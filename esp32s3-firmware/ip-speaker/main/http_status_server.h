#pragma once

#include "esp_err.h"
#include "ring_buffer.h"

// Arranca esp_http_server en modo STA normal con:
//   GET  /status  -> JSON con estado, RSSI, volumen, timestamps, uptime
//   POST /volume  -> {"volume_percent": 0-100}, ajusta y persiste en NVS
// `rb` se usa solo para estimar el estado idle/streaming (bytes disponibles
// en el ring buffer) hasta que el Hito 3 aporte un estado real vía protocolo.
esp_err_t http_status_server_start(ring_buffer_t *rb);
