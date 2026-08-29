#include "volume_storage.h"

#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "volume_storage";
#define NVS_NAMESPACE "ipspk_cfg"
#define NVS_KEY_VOLUME "volume"

int volume_storage_load(int default_volume)
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        return default_volume;
    }
    int32_t value = default_volume;
    err = nvs_get_i32(handle, NVS_KEY_VOLUME, &value);
    nvs_close(handle);
    if (err != ESP_OK) {
        return default_volume;
    }
    return (int) value;
}

void volume_storage_save(int volume_percent)
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "nvs_open failed: %s", esp_err_to_name(err));
        return;
    }
    err = nvs_set_i32(handle, NVS_KEY_VOLUME, (int32_t) volume_percent);
    if (err == ESP_OK) {
        err = nvs_commit(handle);
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "No se pudo persistir el volumen: %s", esp_err_to_name(err));
    }
    nvs_close(handle);
}
