#include "time_sync.h"

#include <time.h>
#include <string.h>
#include "esp_netif_sntp.h"
#include "esp_sntp.h"
#include "esp_log.h"

static const char *TAG = "time_sync";
static volatile bool s_synced = false;

esp_err_t time_sync_start_and_wait(uint32_t timeout_ms)
{
    setenv("TZ", "CET-1CEST,M3.5.0,M10.5.0/3", 1);
    tzset();

    esp_sntp_config_t config = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    config.start = true;
    esp_err_t err = esp_netif_sntp_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_netif_sntp_init failed: %s", esp_err_to_name(err));
        return err;
    }

    err = esp_netif_sntp_sync_wait(pdMS_TO_TICKS(timeout_ms));
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Timeout esperando sincronización SNTP");
        return err;
    }
    s_synced = true;
    char now_str[24];
    time_sync_format_now(now_str, sizeof(now_str));
    ESP_LOGI(TAG, "Hora sincronizada: %s", now_str);
    return ESP_OK;
}

bool time_sync_is_synced(void)
{
    return s_synced;
}

static void format_time_t(time_t t, char *buf, size_t buf_len)
{
    struct tm timeinfo;
    localtime_r(&t, &timeinfo);
    strftime(buf, buf_len, "%d/%m/%Y - %H:%M:%S", &timeinfo);
}

void time_sync_format_now(char *buf, size_t buf_len)
{
    if (!s_synced) {
        snprintf(buf, buf_len, "null");
        return;
    }
    time_t now;
    time(&now);
    format_time_t(now, buf, buf_len);
}

void time_sync_format_ago_ms(int64_t ago_ms, char *buf, size_t buf_len)
{
    if (!s_synced) {
        snprintf(buf, buf_len, "null");
        return;
    }
    time_t now;
    time(&now);
    // ago_ms es un delta de reloj monótono (esp_timer_get_time()), con
    // resolución de segundo basta para el uso (mostrar "hace cuánto" en el
    // JSON de /status) sin complicar el formateo con sub-segundos.
    time_t event_time = now - (time_t) (ago_ms / 1000);
    format_time_t(event_time, buf, buf_len);
}
