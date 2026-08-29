#include "esp_log.h"
#include "esp_heap_caps.h"

#include "wifi_manager.h"
#include "audio_codec_es8311.h"
#include "ring_buffer.h"
#include "i2s_player.h"
#include "udp_audio_server.h"
#include "time_sync.h"
#include "volume_storage.h"
#include "http_status_server.h"

static const char *TAG = "ip-speaker";

// ~2s de margen a 16kHz/mono/16-bit (32KB/s) para absorber jitter de red.
#define RING_BUFFER_CAPACITY_BYTES (64 * 1024)

static ring_buffer_t s_ring_buffer;

void app_main(void)
{
    ESP_LOGI(TAG, "Arrancando ip-speaker (Hito 1: WiFi + UDP + PCM crudo)");

    ESP_ERROR_CHECK(audio_codec_es8311_init());
    ESP_LOGI(TAG, "Reproduciendo tono de prueba (440Hz, 1s)...");
    i2s_player_play_test_tone(440, 1000);

    ESP_ERROR_CHECK(ring_buffer_init(&s_ring_buffer, RING_BUFFER_CAPACITY_BYTES));
    ESP_LOGI(TAG, "PSRAM libre tras reservar el ring buffer: %u bytes",
             (unsigned) heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    esp_err_t wifi_err = wifi_manager_start_and_wait(15000);
    if (wifi_err != ESP_OK) {
        ESP_LOGE(TAG, "No se pudo conectar a WiFi, reintentando en segundo plano...");
    }

    char ip_str[16];
    wifi_manager_get_ip_str(ip_str, sizeof(ip_str));
    ESP_LOGI(TAG, "IP del altavoz: %s", ip_str);

    if (wifi_err == ESP_OK) {
        time_sync_start_and_wait(10000);
    }

    // El volumen del test tone (Hito 1) usó un valor fijo antes de que NVS
    // estuviera disponible; aquí lo sobreescribimos con el último valor
    // persistido (o 60% si es la primera vez que arranca).
    int saved_volume = volume_storage_load(60);
    audio_codec_set_volume(saved_volume);

    audio_codec_set_pa_enabled(true);
    ESP_ERROR_CHECK(i2s_player_start(&s_ring_buffer));
    ESP_ERROR_CHECK(udp_audio_server_start(&s_ring_buffer));
    ESP_ERROR_CHECK(http_status_server_start(&s_ring_buffer));

    ESP_LOGI(TAG, "Listo. Envía PCM 16kHz/mono/16-bit por UDP al puerto %d, status en http://%s/status",
             UDP_AUDIO_SERVER_PORT, ip_str);
}
