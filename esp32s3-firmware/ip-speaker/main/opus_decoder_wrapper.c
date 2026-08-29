#include "opus_decoder_wrapper.h"
#include "audio_codec_es8311.h" // AUDIO_SAMPLE_RATE_HZ, AUDIO_CHANNELS

#include "opus.h"
#include "esp_log.h"

static const char *TAG = "opus_decoder";
static OpusDecoder *s_decoder = NULL;

esp_err_t opus_decoder_wrapper_init(void)
{
    int err = 0;
    s_decoder = opus_decoder_create(AUDIO_SAMPLE_RATE_HZ, AUDIO_CHANNELS, &err);
    if (s_decoder == NULL || err != OPUS_OK) {
        ESP_LOGE(TAG, "opus_decoder_create failed: %d", err);
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "Decoder Opus listo (%d Hz, %d canal(es), frames de %d muestras)",
             AUDIO_SAMPLE_RATE_HZ, AUDIO_CHANNELS, OPUS_FRAME_SAMPLES);
    return ESP_OK;
}

int opus_decoder_wrapper_decode(const uint8_t *data, int len, int16_t *pcm_out)
{
    return opus_decode(s_decoder, data, len, pcm_out, OPUS_FRAME_SAMPLES, 0);
}

int opus_decoder_wrapper_conceal(int16_t *pcm_out)
{
    // data==NULL, len=0 le indica a libopus que genere audio de relleno
    // (PLC) para un frame perdido, en vez de dejarlo en silencio.
    return opus_decode(s_decoder, NULL, 0, pcm_out, OPUS_FRAME_SAMPLES, 0);
}
