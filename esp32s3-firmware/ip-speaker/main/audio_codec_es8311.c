#include "audio_codec_es8311.h"
#include "board_pins.h"

#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "esp_io_expander_tca95xx_16bit.h"
#include "esp_codec_dev_defaults.h"
#include "esp_log.h"

static const char *TAG = "audio_codec_es8311";

static i2c_master_bus_handle_t s_i2c_bus = NULL;
static esp_io_expander_handle_t s_io_expander = NULL;
static i2s_chan_handle_t s_i2s_tx_handle = NULL;
static esp_codec_dev_handle_t s_play_dev = NULL;

static esp_err_t init_i2c_bus(void)
{
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = BOARD_I2C_PORT,
        .sda_io_num = BOARD_I2C_SDA_GPIO,
        .scl_io_num = BOARD_I2C_SCL_GPIO,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    return i2c_new_master_bus(&bus_cfg, &s_i2c_bus);
}

static esp_err_t init_tca9555(void)
{
    esp_err_t err = esp_io_expander_new_i2c_tca95xx_16bit(s_i2c_bus, BOARD_TCA9555_I2C_ADDR, &s_io_expander);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "TCA9555 init failed: %s", esp_err_to_name(err));
        return err;
    }
    err = esp_io_expander_set_dir(s_io_expander, IO_EXPANDER_PIN_NUM_8, IO_EXPANDER_OUTPUT);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "TCA9555 set PA_CTRL direction failed: %s", esp_err_to_name(err));
        return err;
    }
    // Amplificador apagado hasta que se llame explícitamente a audio_codec_set_pa_enabled(true).
    return esp_io_expander_set_level(s_io_expander, IO_EXPANDER_PIN_NUM_8, 0);
}

static esp_err_t init_i2s_tx(void)
{
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    esp_err_t err = i2s_new_channel(&chan_cfg, &s_i2s_tx_handle, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2s_new_channel failed: %s", esp_err_to_name(err));
        return err;
    }

    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE_HZ),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(
            AUDIO_BITS_PER_SAMPLE,
            AUDIO_CHANNELS == 1 ? I2S_SLOT_MODE_MONO : I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = BOARD_I2S_MCLK_GPIO,
            .bclk = BOARD_I2S_BCLK_GPIO,
            .ws = BOARD_I2S_WS_GPIO,
            .dout = BOARD_I2S_DOUT_GPIO,
            .din = I2S_GPIO_UNUSED,
        },
    };
    err = i2s_channel_init_std_mode(s_i2s_tx_handle, &std_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_init_std_mode failed: %s", esp_err_to_name(err));
        return err;
    }
    return i2s_channel_enable(s_i2s_tx_handle);
}

static esp_err_t init_codec_dev(void)
{
    audio_codec_i2c_cfg_t i2c_cfg = {
        .port = BOARD_I2C_PORT,
        .addr = ES8311_CODEC_DEFAULT_ADDR,
        .bus_handle = s_i2c_bus,
    };
    const audio_codec_ctrl_if_t *ctrl_if = audio_codec_new_i2c_ctrl(&i2c_cfg);
    if (ctrl_if == NULL) {
        ESP_LOGE(TAG, "audio_codec_new_i2c_ctrl failed");
        return ESP_FAIL;
    }

    const audio_codec_gpio_if_t *gpio_if = audio_codec_new_gpio();

    audio_codec_i2s_cfg_t i2s_cfg = {
        .port = 0, // I2S_NUM_0, el único canal que abrimos
        .tx_handle = s_i2s_tx_handle,
        .rx_handle = NULL,
    };
    const audio_codec_data_if_t *data_if = audio_codec_new_i2s_data(&i2s_cfg);
    if (data_if == NULL) {
        ESP_LOGE(TAG, "audio_codec_new_i2s_data failed");
        return ESP_FAIL;
    }

    es8311_codec_cfg_t es8311_cfg = {
        .codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC,
        .ctrl_if = ctrl_if,
        .gpio_if = gpio_if,
        .pa_pin = -1, // PA_CTRL no es un GPIO directo: lo gestionamos nosotros vía TCA9555.
        .use_mclk = true,
    };
    const audio_codec_if_t *codec_if = es8311_codec_new(&es8311_cfg);
    if (codec_if == NULL) {
        ESP_LOGE(TAG, "es8311_codec_new failed");
        return ESP_FAIL;
    }

    esp_codec_dev_cfg_t dev_cfg = {
        .dev_type = ESP_CODEC_DEV_TYPE_OUT,
        .codec_if = codec_if,
        .data_if = data_if,
    };
    s_play_dev = esp_codec_dev_new(&dev_cfg);
    if (s_play_dev == NULL) {
        ESP_LOGE(TAG, "esp_codec_dev_new failed");
        return ESP_FAIL;
    }

    esp_codec_dev_sample_info_t fs = {
        .bits_per_sample = AUDIO_BITS_PER_SAMPLE,
        .channel = AUDIO_CHANNELS,
        .sample_rate = AUDIO_SAMPLE_RATE_HZ,
    };
    int ret = esp_codec_dev_open(s_play_dev, &fs);
    if (ret != 0) {
        ESP_LOGE(TAG, "esp_codec_dev_open failed: %d", ret);
        return ESP_FAIL;
    }
    return esp_codec_dev_set_out_vol(s_play_dev, 60) == 0 ? ESP_OK : ESP_FAIL;
}

esp_err_t audio_codec_es8311_init(void)
{
    esp_err_t err = init_i2c_bus();
    if (err != ESP_OK) {
        return err;
    }
    err = init_tca9555();
    if (err != ESP_OK) {
        return err;
    }
    err = init_i2s_tx();
    if (err != ESP_OK) {
        return err;
    }
    err = init_codec_dev();
    if (err != ESP_OK) {
        return err;
    }
    ESP_LOGI(TAG, "ES8311 listo (%d Hz, %d canal(es), %d bits)", AUDIO_SAMPLE_RATE_HZ, AUDIO_CHANNELS, AUDIO_BITS_PER_SAMPLE);
    return ESP_OK;
}

esp_err_t audio_codec_write(const void *data, size_t len)
{
    if (s_play_dev == NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    int ret = esp_codec_dev_write(s_play_dev, (void *)data, (int)len);
    return ret == 0 ? ESP_OK : ESP_FAIL;
}

esp_err_t audio_codec_set_pa_enabled(bool enabled)
{
    if (s_io_expander == NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    return esp_io_expander_set_level(s_io_expander, IO_EXPANDER_PIN_NUM_8, enabled ? 1 : 0);
}

esp_err_t audio_codec_set_volume(int volume_percent)
{
    if (s_play_dev == NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    if (volume_percent < 0) volume_percent = 0;
    if (volume_percent > 100) volume_percent = 100;
    return esp_codec_dev_set_out_vol(s_play_dev, volume_percent) == 0 ? ESP_OK : ESP_FAIL;
}

esp_err_t audio_codec_get_volume(int *volume_percent)
{
    if (s_play_dev == NULL || volume_percent == NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    return esp_codec_dev_get_out_vol(s_play_dev, volume_percent) == 0 ? ESP_OK : ESP_FAIL;
}
