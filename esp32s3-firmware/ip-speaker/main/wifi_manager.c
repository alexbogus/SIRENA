#include "wifi_manager.h"
#include "wifi_credentials.h"
#include "nvs_config.h"
#include "board_pins.h"

#include <string.h>
#include <stdio.h>
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"

static const char *TAG = "wifi_manager";

static EventGroupHandle_t s_wifi_event_group;
static const int WIFI_CONNECTED_BIT = BIT0;
static esp_netif_t *s_sta_netif = NULL;
static esp_netif_t *s_ap_netif = NULL;
static volatile bool s_connected = false;
static volatile bool s_static_ip = false;

static void event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        s_connected = false;
        ESP_LOGW(TAG, "WiFi desconectado, reintentando...");
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_CONNECTED && s_static_ip) {
        // Con IP estática no llega IP_EVENT_STA_GOT_IP (DHCP client parado),
        // así que confirmamos la conexión aquí directamente.
        s_connected = true;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *) event_data;
        ESP_LOGI(TAG, "IP obtenida: " IPSTR, IP2STR(&event->ip_info.ip));
        s_connected = true;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

static bool boot_button_held(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = 1ULL << BOARD_BOOT_BUTTON_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    gpio_config(&io_conf);
    vTaskDelay(pdMS_TO_TICKS(50)); // deja asentar el pull-up antes de leer
    return gpio_get_level(BOARD_BOOT_BUTTON_GPIO) == 0; // activo a nivel bajo
}

static void apply_static_ip(const nvs_wifi_config_t *cfg)
{
    esp_netif_dhcpc_stop(s_sta_netif);
    esp_netif_ip_info_t ip_info = {0};
    esp_netif_str_to_ip4(cfg->static_ip, &ip_info.ip);
    esp_netif_str_to_ip4(cfg->gateway, &ip_info.gw);
    esp_netif_str_to_ip4(cfg->netmask, &ip_info.netmask);
    esp_netif_set_ip_info(s_sta_netif, &ip_info);
    s_static_ip = true;
    ESP_LOGI(TAG, "IP estática configurada: %s (gw %s, mask %s)", cfg->static_ip, cfg->gateway, cfg->netmask);
}

static wifi_manager_result_t try_connect_sta(uint32_t timeout_ms)
{
    nvs_wifi_config_t nvs_cfg;
    bool has_nvs_cfg = nvs_config_load(&nvs_cfg);

    wifi_config_t wifi_config = {0};
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    if (has_nvs_cfg) {
        ESP_LOGI(TAG, "Usando credenciales guardadas en NVS (SSID: %s)", nvs_cfg.ssid);
        strlcpy((char *) wifi_config.sta.ssid, nvs_cfg.ssid, sizeof(wifi_config.sta.ssid));
        strlcpy((char *) wifi_config.sta.password, nvs_cfg.password, sizeof(wifi_config.sta.password));
    } else {
        ESP_LOGI(TAG, "Sin credenciales en NVS, usando las compiladas en wifi_credentials.h");
        strlcpy((char *) wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid));
        strlcpy((char *) wifi_config.sta.password, WIFI_PASSWORD, sizeof(wifi_config.sta.password));
    }

    if (wifi_config.sta.ssid[0] == '\0') {
        ESP_LOGW(TAG, "No hay SSID configurado (ni en NVS ni compilado)");
        return WIFI_MANAGER_AP_CONFIG;
    }

    if (has_nvs_cfg && nvs_cfg.use_static_ip && nvs_cfg.static_ip[0] != '\0') {
        apply_static_ip(&nvs_cfg);
    }

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT,
                                            pdFALSE, pdTRUE, pdMS_TO_TICKS(timeout_ms));
    if (!(bits & WIFI_CONNECTED_BIT)) {
        ESP_LOGE(TAG, "Timeout esperando conexión WiFi");
        return WIFI_MANAGER_AP_CONFIG;
    }

    // El modem-sleep por defecto introduce jitter variable en la recepción UDP
    // al apagar el radio entre balizas; lo desactivamos para audio en tiempo real.
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    return WIFI_MANAGER_STA_CONNECTED;
}

static void start_ap_config_mode(void)
{
    s_ap_netif = esp_netif_create_default_wifi_ap();

    uint8_t mac[6];
    esp_wifi_get_mac(WIFI_IF_STA, mac);

    wifi_config_t ap_config = {0};
    int len = snprintf((char *) ap_config.ap.ssid, sizeof(ap_config.ap.ssid),
                        "IPSpeaker-Config-%02X%02X", mac[4], mac[5]);
    ap_config.ap.ssid_len = len;
    ap_config.ap.channel = 1;
    ap_config.ap.max_connection = 4;
    ap_config.ap.authmode = WIFI_AUTH_OPEN; // portal temporal de configuración, deuda técnica de seguridad como el resto del MVP

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGW(TAG, "Modo AP de configuración activo: SSID \"%s\" (sin contraseña), IP 192.168.4.1",
             (char *) ap_config.ap.ssid);
}

wifi_manager_result_t wifi_manager_start(uint32_t timeout_ms)
{
    esp_err_t nvs_err = nvs_flash_init();
    if (nvs_err == ESP_ERR_NVS_NO_FREE_PAGES || nvs_err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        nvs_err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(nvs_err);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    s_sta_netif = esp_netif_create_default_wifi_sta();

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

    s_wifi_event_group = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL));

    if (boot_button_held()) {
        ESP_LOGW(TAG, "Botón BOOT mantenido pulsado en el arranque: forzando modo AP de configuración");
        start_ap_config_mode();
        return WIFI_MANAGER_AP_CONFIG;
    }

    wifi_manager_result_t result = try_connect_sta(timeout_ms);
    if (result == WIFI_MANAGER_AP_CONFIG) {
        start_ap_config_mode();
    }
    return result;
}

bool wifi_manager_is_connected(void)
{
    return s_connected;
}

void wifi_manager_get_ip_str(char *buf, size_t buf_len)
{
    esp_netif_ip_info_t ip_info;
    esp_netif_t *active_netif = s_ap_netif != NULL ? s_ap_netif : s_sta_netif;
    if (active_netif != NULL && esp_netif_get_ip_info(active_netif, &ip_info) == ESP_OK) {
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
