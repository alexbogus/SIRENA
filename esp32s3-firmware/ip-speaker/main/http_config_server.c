#include "http_config_server.h"
#include "nvs_config.h"

#include <string.h>
#include <stdlib.h>
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "http_config_server";

static const char FORM_HTML[] =
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<title>Configuracion ip-speaker</title></head><body>"
    "<h1>Configuracion del altavoz</h1>"
    "<form method=\"POST\" action=\"/save\">"
    "<label>SSID WiFi:<br><input name=\"ssid\" required></label><br><br>"
    "<label>Password WiFi:<br><input name=\"password\" type=\"password\"></label><br><br>"
    "<label>Identificador del altavoz (opcional, ej. poblacion):<br>"
    "<input name=\"speaker_id\"></label><br><br>"
    "<label><input type=\"checkbox\" name=\"use_static_ip\" value=\"1\"> Usar IP estatica</label><br><br>"
    "<label>IP estatica:<br><input name=\"static_ip\" placeholder=\"192.168.1.50\"></label><br><br>"
    "<label>Puerta de enlace:<br><input name=\"gateway\" placeholder=\"192.168.1.1\"></label><br><br>"
    "<label>Mascara de red:<br><input name=\"netmask\" placeholder=\"255.255.255.0\"></label><br><br>"
    "<button type=\"submit\">Guardar y reiniciar</button>"
    "</form></body></html>";

static void url_decode(char *dst, const char *src)
{
    while (*src) {
        if (*src == '%' && src[1] && src[2]) {
            char hex[3] = {src[1], src[2], 0};
            *dst++ = (char) strtol(hex, NULL, 16);
            src += 3;
        } else if (*src == '+') {
            *dst++ = ' ';
            src++;
        } else {
            *dst++ = *src++;
        }
    }
    *dst = '\0';
}

// Busca `key=` en `body` (formato application/x-www-form-urlencoded) y
// copia el valor decodificado en `out`. Deja `out` vacío si no se encuentra.
static void form_get(const char *body, const char *key, char *out, size_t out_len)
{
    out[0] = '\0';
    char search[64];
    snprintf(search, sizeof(search), "%s=", key);
    const char *start = strstr(body, search);
    if (start == NULL) {
        return;
    }
    start += strlen(search);
    const char *end = strchr(start, '&');
    size_t raw_len = end != NULL ? (size_t)(end - start) : strlen(start);
    if (raw_len >= out_len * 3) { // margen para el peor caso de %XX
        raw_len = out_len * 3 - 1;
    }
    char raw[192];
    if (raw_len >= sizeof(raw)) {
        raw_len = sizeof(raw) - 1;
    }
    memcpy(raw, start, raw_len);
    raw[raw_len] = '\0';
    char decoded[192];
    url_decode(decoded, raw);
    strlcpy(out, decoded, out_len);
}

static esp_err_t form_get_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, FORM_HTML, sizeof(FORM_HTML) - 1);
    return ESP_OK;
}

static void restart_task(void *arg)
{
    vTaskDelay(pdMS_TO_TICKS(1500)); // deja tiempo a que el navegador reciba la respuesta
    esp_restart();
}

static esp_err_t save_post_handler(httpd_req_t *req)
{
    char body[512];
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

    nvs_wifi_config_t cfg = {0};
    form_get(body, "ssid", cfg.ssid, sizeof(cfg.ssid));
    form_get(body, "password", cfg.password, sizeof(cfg.password));
    form_get(body, "speaker_id", cfg.speaker_id, sizeof(cfg.speaker_id));
    form_get(body, "static_ip", cfg.static_ip, sizeof(cfg.static_ip));
    form_get(body, "gateway", cfg.gateway, sizeof(cfg.gateway));
    form_get(body, "netmask", cfg.netmask, sizeof(cfg.netmask));

    char use_static[4];
    form_get(body, "use_static_ip", use_static, sizeof(use_static));
    cfg.use_static_ip = use_static[0] == '1';

    if (cfg.ssid[0] == '\0') {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "El SSID es obligatorio");
        return ESP_FAIL;
    }

    esp_err_t err = nvs_config_save(&cfg);
    if (err != ESP_OK) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    const char *resp = "<html><body><h1>Configuracion guardada</h1>"
                        "<p>El altavoz se reiniciara y tratara de conectar a la red indicada.</p>"
                        "</body></html>";
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);

    ESP_LOGI(TAG, "Configuración guardada (SSID: %s), reiniciando...", cfg.ssid);
    xTaskCreate(restart_task, "restart_task", 2048, NULL, 5, NULL);
    return ESP_OK;
}

esp_err_t http_config_server_start(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    httpd_handle_t server = NULL;
    esp_err_t err = httpd_start(&server, &config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "httpd_start failed: %s", esp_err_to_name(err));
        return err;
    }

    httpd_uri_t form_uri = {.uri = "/", .method = HTTP_GET, .handler = form_get_handler};
    httpd_register_uri_handler(server, &form_uri);

    httpd_uri_t save_uri = {.uri = "/save", .method = HTTP_POST, .handler = save_post_handler};
    httpd_register_uri_handler(server, &save_uri);

    ESP_LOGI(TAG, "Portal de configuración disponible en http://192.168.4.1/");
    return ESP_OK;
}
