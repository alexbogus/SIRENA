#pragma once

#include "esp_err.h"

// Arranca esp_http_server en modo AP con un formulario mínimo (SSID,
// password, IP estática opcional, speaker_id). Al enviarlo, guarda en NVS
// (nvs_config.c) y reinicia el dispositivo para aplicar la nueva config.
esp_err_t http_config_server_start(void);
