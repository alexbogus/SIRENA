#include "http_status_server.h"

#include <string.h>
#include <stdlib.h>
#include "esp_http_server.h"
#include "esp_timer.h"
#include "esp_log.h"

#include "firmware_version.h"
#include "wifi_manager.h"
#include "time_sync.h"
#include "audio_codec_es8311.h"
#include "volume_storage.h"
#include "udp_audio_server.h"

static const char *TAG = "http_status_server";

static esp_err_t status_get_handler(httpd_req_t *req)
{
    char ip_str[16];
    wifi_manager_get_ip_str(ip_str, sizeof(ip_str));

    int8_t rssi_dbm = 0;
    wifi_manager_get_rssi(&rssi_dbm);

    int volume_percent = 0;
    audio_codec_get_volume(&volume_percent);

    const char *state = udp_audio_server_is_streaming() ? "streaming" : "idle";

    char last_message_at[24];
    int64_t last_msg_ms = udp_audio_server_get_last_message_time_ms();
    if (last_msg_ms == 0 || !time_sync_is_synced()) {
        snprintf(last_message_at, sizeof(last_message_at), "null");
    } else {
        // Aproximación: usamos la hora actual formateada ya que solo
        // guardamos el timestamp del último mensaje en milisegundos de
        // uptime, no en tiempo de pared. Suficiente para el Hito 2; con el
        // protocolo del Hito 3 esto se puede afinar si hace falta.
        time_sync_format_now(last_message_at, sizeof(last_message_at));
    }

    char last_healthcheck_at[24];
    time_sync_format_now(last_healthcheck_at, sizeof(last_healthcheck_at));

    int64_t uptime_seconds = esp_timer_get_time() / 1000000;

    char json[512];
    int len = snprintf(json, sizeof(json),
        "{"
        "\"firmware_version\":\"%s\","
        "\"ip\":\"%s\","
        "\"rssi_dbm\":%d,"
        "\"state\":\"%s\","
        "\"volume_percent\":%d,"
        "\"last_message_at\":%s%s%s,"
        "\"last_healthcheck_at\":\"%s\","
        "\"uptime_seconds\":%lld"
        "}",
        FIRMWARE_VERSION,
        ip_str,
        rssi_dbm,
        state,
        volume_percent,
        strcmp(last_message_at, "null") == 0 ? "" : "\"",
        last_message_at,
        strcmp(last_message_at, "null") == 0 ? "" : "\"",
        last_healthcheck_at,
        (long long) uptime_seconds);

    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, json, len);
    return ESP_OK;
}

static esp_err_t volume_post_handler(httpd_req_t *req)
{
    char body[128];
    int total = req->content_len < (int) sizeof(body) - 1 ? req->content_len : (int) sizeof(body) - 1;
    int received = 0;
    while (received < total) {
        int r = httpd_req_recv(req, body + received, total - received);
        if (r <= 0) {
            httpd_resp_send_500(req);
            return ESP_FAIL;
        }
        received += r;
    }
    body[received] = '\0';

    const char *key = strstr(body, "volume_percent");
    if (key == NULL) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "falta volume_percent");
        return ESP_FAIL;
    }
    const char *colon = strchr(key, ':');
    if (colon == NULL) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "JSON inválido");
        return ESP_FAIL;
    }
    int volume_percent = (int) strtol(colon + 1, NULL, 10);
    if (volume_percent < 0) volume_percent = 0;
    if (volume_percent > 100) volume_percent = 100;

    esp_err_t err = audio_codec_set_volume(volume_percent);
    if (err != ESP_OK) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    volume_storage_save(volume_percent);

    char json[64];
    int len = snprintf(json, sizeof(json), "{\"volume_percent\":%d}", volume_percent);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, json, len);
    ESP_LOGI(TAG, "Volumen ajustado a %d%% vía HTTP", volume_percent);
    return ESP_OK;
}

esp_err_t http_status_server_start(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    httpd_handle_t server = NULL;
    esp_err_t err = httpd_start(&server, &config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "httpd_start failed: %s", esp_err_to_name(err));
        return err;
    }

    httpd_uri_t status_uri = {
        .uri = "/status",
        .method = HTTP_GET,
        .handler = status_get_handler,
    };
    httpd_register_uri_handler(server, &status_uri);

    httpd_uri_t volume_uri = {
        .uri = "/volume",
        .method = HTTP_POST,
        .handler = volume_post_handler,
    };
    httpd_register_uri_handler(server, &volume_uri);

    ESP_LOGI(TAG, "Servidor HTTP de status/control arrancado en el puerto 80");
    return ESP_OK;
}
