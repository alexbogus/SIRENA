#pragma once

#include "esp_err.h"

// Arranca esp_http_server en modo STA normal con:
//   GET  /status  -> JSON con estado, RSSI, volumen, timestamps, uptime
//   POST /volume  -> {"volume_percent": 0-100}, ajusta y persiste en NVS
// El campo "state" (idle/streaming) refleja el estado real del protocolo
// (udp_audio_server_is_streaming()), no una estimación.
esp_err_t http_status_server_start(void);
