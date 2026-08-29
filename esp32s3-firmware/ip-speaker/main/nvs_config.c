#include "nvs_config.h"

#include <string.h>
#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "nvs_config";
#define NVS_NAMESPACE "ipspk_cfg"

static esp_err_t get_str(nvs_handle_t h, const char *key, char *out, size_t out_len)
{
    size_t len = out_len;
    return nvs_get_str(h, key, out, &len);
}

bool nvs_config_load(nvs_wifi_config_t *out)
{
    memset(out, 0, sizeof(*out));

    nvs_handle_t h;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &h) != ESP_OK) {
        return false;
    }

    esp_err_t ssid_err = get_str(h, "wifi_ssid", out->ssid, sizeof(out->ssid));
    if (ssid_err != ESP_OK || out->ssid[0] == '\0') {
        nvs_close(h);
        return false; // sin SSID guardado, no hay config válida
    }

    get_str(h, "wifi_pass", out->password, sizeof(out->password));

    uint8_t use_static = 0;
    nvs_get_u8(h, "use_static_ip", &use_static);
    out->use_static_ip = use_static != 0;

    get_str(h, "static_ip", out->static_ip, sizeof(out->static_ip));
    get_str(h, "gateway", out->gateway, sizeof(out->gateway));
    get_str(h, "netmask", out->netmask, sizeof(out->netmask));
    get_str(h, "speaker_id", out->speaker_id, sizeof(out->speaker_id));

    nvs_close(h);
    return true;
}

esp_err_t nvs_config_save(const nvs_wifi_config_t *cfg)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs_open failed: %s", esp_err_to_name(err));
        return err;
    }

    nvs_set_str(h, "wifi_ssid", cfg->ssid);
    nvs_set_str(h, "wifi_pass", cfg->password);
    nvs_set_u8(h, "use_static_ip", cfg->use_static_ip ? 1 : 0);
    nvs_set_str(h, "static_ip", cfg->static_ip);
    nvs_set_str(h, "gateway", cfg->gateway);
    nvs_set_str(h, "netmask", cfg->netmask);
    nvs_set_str(h, "speaker_id", cfg->speaker_id);

    err = nvs_commit(h);
    nvs_close(h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "No se pudo persistir la configuración: %s", esp_err_to_name(err));
    }
    return err;
}

esp_err_t nvs_config_clear(void)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    nvs_erase_key(h, "wifi_ssid");
    nvs_erase_key(h, "wifi_pass");
    nvs_erase_key(h, "use_static_ip");
    nvs_erase_key(h, "static_ip");
    nvs_erase_key(h, "gateway");
    nvs_erase_key(h, "netmask");
    nvs_erase_key(h, "speaker_id");
    err = nvs_commit(h);
    nvs_close(h);
    return err;
}
