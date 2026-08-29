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
#include "http_config_server.h"
#include "opus_decoder_wrapper.h"
#include "led_ring.h"

static const char *TAG = "ip-speaker";

// ~2s de margen a 16kHz/mono/16-bit (32KB/s) para absorber jitter de red.
#define RING_BUFFER_CAPACITY_BYTES (64 * 1024)

static ring_buffer_t s_ring_buffer;

void app_main(void)
{
    ESP_LOGI(TAG, "Arrancando ip-speaker");

    ESP_ERROR_CHECK(audio_codec_es8311_init());
    ESP_ERROR_CHECK(led_ring_init());
    ESP_LOGI(TAG, "Reproduciendo tono de prueba (440Hz, 1s)...");
    i2s_player_play_test_tone(440, 1000);

    ESP_ERROR_CHECK(ring_buffer_init(&s_ring_buffer, RING_BUFFER_CAPACITY_BYTES));
    ESP_ERROR_CHECK(opus_decoder_wrapper_init());
    ESP_LOGI(TAG, "PSRAM libre tras reservar el ring buffer: %u bytes",
             (unsigned) heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    wifi_manager_result_t wifi_result = wifi_manager_start(15000);

    char ip_str[16];
    wifi_manager_get_ip_str(ip_str, sizeof(ip_str));

    if (wifi_result == WIFI_MANAGER_AP_CONFIG) {
        // Modo portal de configuración: es una red WiFi propia y aislada
        // (no la LAN donde vive el Docker), así que no tiene sentido
        // arrancar aquí el resto del pipeline (UDP de audio, status server)
        // -- solo el formulario de configuración. El dispositivo se
        // reinicia solo tras guardar la config (ver http_config_server.c).
        ESP_LOGW(TAG, "Sin conexión WiFi válida: modo portal de configuración en http://%s/", ip_str);
        ESP_ERROR_CHECK(http_config_server_start());
        return;
    }

    ESP_LOGI(TAG, "IP del altavoz: %s", ip_str);
    time_sync_start_and_wait(10000);

    // El volumen del test tone (Hito 1) usó un valor fijo antes de que NVS
    // estuviera disponible; aquí lo sobreescribimos con el último valor
    // persistido (o 60% si es la primera vez que arranca).
    int saved_volume = volume_storage_load(60);
    audio_codec_set_volume(saved_volume);

    audio_codec_set_pa_enabled(true);
    ESP_ERROR_CHECK(i2s_player_start(&s_ring_buffer));
    ESP_ERROR_CHECK(udp_audio_server_start(&s_ring_buffer));
    ESP_ERROR_CHECK(http_status_server_start());

    ESP_LOGI(TAG, "Listo. Envía PCM/Opus por UDP al puerto %d, status en http://%s/status",
             UDP_AUDIO_SERVER_PORT, ip_str);
}
