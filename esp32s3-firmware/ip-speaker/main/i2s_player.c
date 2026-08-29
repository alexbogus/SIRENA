#include "i2s_player.h"
#include "audio_codec_es8311.h"

#include <math.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "i2s_player";

// Bloque de lectura del ring buffer: 20ms a 16kHz/mono/16-bit = 640 bytes.
// Mismo tamaño que usaremos para los frames Opus en el Hito 4.
#define PLAYBACK_BLOCK_BYTES (640)
#define PLAYBACK_TASK_STACK  (4096)
#define PLAYBACK_TASK_PRIO   (15)
#define UDP_RX_TASK_CORE     (0)
#define PLAYBACK_TASK_CORE   (1)

static void playback_task(void *arg)
{
    ring_buffer_t *rb = (ring_buffer_t *) arg;
    uint8_t *block = heap_caps_malloc(PLAYBACK_BLOCK_BYTES, MALLOC_CAP_SPIRAM);
    if (block == NULL) {
        ESP_LOGE(TAG, "No se pudo reservar el bloque de reproducción");
        vTaskDelete(NULL);
        return;
    }

    uint32_t last_log_ms = 0;
    while (1) {
        ring_buffer_read_or_silence(rb, block, PLAYBACK_BLOCK_BYTES);
        audio_codec_write(block, PLAYBACK_BLOCK_BYTES);

        uint32_t now_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;
        if (now_ms - last_log_ms > 5000) {
            ESP_LOGI(TAG, "underruns=%lu overruns=%lu disponible=%u bytes",
                     (unsigned long) rb->underrun_count, (unsigned long) rb->overrun_count,
                     (unsigned) ring_buffer_bytes_available(rb));
            last_log_ms = now_ms;
        }
    }
}

esp_err_t i2s_player_start(ring_buffer_t *rb)
{
    BaseType_t ok = xTaskCreatePinnedToCore(playback_task, "i2s_playback", PLAYBACK_TASK_STACK,
                                             rb, PLAYBACK_TASK_PRIO, NULL, PLAYBACK_TASK_CORE);
    return ok == pdPASS ? ESP_OK : ESP_FAIL;
}

esp_err_t i2s_player_play_test_tone(int freq_hz, int duration_ms)
{
    const int sample_rate = AUDIO_SAMPLE_RATE_HZ;
    const int total_samples = (sample_rate * duration_ms) / 1000;
    const int block_samples = 320; // 20ms a 16kHz
    int16_t block[block_samples];

    audio_codec_set_pa_enabled(true);

    int sample_index = 0;
    while (sample_index < total_samples) {
        int samples_this_block = total_samples - sample_index;
        if (samples_this_block > block_samples) {
            samples_this_block = block_samples;
        }
        for (int i = 0; i < samples_this_block; i++) {
            double t = (double)(sample_index + i) / sample_rate;
            block[i] = (int16_t)(3000.0 * sin(2.0 * M_PI * freq_hz * t));
        }
        esp_err_t err = audio_codec_write(block, samples_this_block * sizeof(int16_t));
        if (err != ESP_OK) {
            return err;
        }
        sample_index += samples_this_block;
    }
    return ESP_OK;
}
