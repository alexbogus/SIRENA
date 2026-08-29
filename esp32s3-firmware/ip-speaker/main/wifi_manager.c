#include "wifi_manager.h"
#include "wifi_credentials.h"

#include <string.h>
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

static const char *TAG = "wifi_manager";

static EventGroupHandle_t s_wifi_event_group;
static const int WIFI_CONNECTED_BIT = BIT0;
static esp_netif_t *s_netif = NULL;
static volatile bool s_connected = false;

static void event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        s_connected = false;
        ESP_LOGW(TAG, "WiFi desconectado, reintentando...");
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *) event_data;
        ESP_LOGI(TAG, "IP obtenida: " IPSTR, IP2STR(&event->ip_info.ip));
        s_connected = true;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

esp_err_t wifi_manager_start_and_wait(uint32_t timeout_ms)
{
    esp_err_t nvs_err = nvs_flash_init();
    if (nvs_err == ESP_ERR_NVS_NO_FREE_PAGES || nvs_err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        // La partición NVS quedó en un estado inconsistente (p.ej. tras cambiar
        // de tamaño de partición): se borra y se reintenta una vez.
        ESP_ERROR_CHECK(nvs_flash_erase());
        nvs_err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(nvs_err);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    s_netif = esp_netif_create_default_wifi_sta();

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

    s_wifi_event_group = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT,
                                            pdFALSE, pdTRUE, pdMS_TO_TICKS(timeout_ms));
    if (!(bits & WIFI_CONNECTED_BIT)) {
        ESP_LOGE(TAG, "Timeout esperando conexión WiFi");
        return ESP_ERR_TIMEOUT;
    }

    // El modem-sleep por defecto introduce jitter variable en la recepción UDP
    // al apagar el radio entre balizas; lo desactivamos para audio en tiempo real.
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    return ESP_OK;
}

bool wifi_manager_is_connected(void)
{
    return s_connected;
}

void wifi_manager_get_ip_str(char *buf, size_t buf_len)
{
    esp_netif_ip_info_t ip_info;
    if (s_netif != NULL && s_connected && esp_netif_get_ip_info(s_netif, &ip_info) == ESP_OK) {
        snprintf(buf, buf_len, IPSTR, IP2STR(&ip_info.ip));
    } else {
        snprintf(buf, buf_len, "0.0.0.0");
    }
}

esp_err_t wifi_manager_get_rssi(int8_t *rssi_dbm)
{
    if (!s_connected) {
        return ESP_FAIL;
    }
    wifi_ap_record_t ap_info;
    esp_err_t err = esp_wifi_sta_get_ap_info(&ap_info);
    if (err == ESP_OK) {
        *rssi_dbm = ap_info.rssi;
    }
    return err;
}
