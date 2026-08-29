#pragma once

#include "esp_err.h"
#include "ring_buffer.h"

#define UDP_AUDIO_SERVER_PORT (5005)

// Arranca la tarea de recepción UDP (core 0). Hito 1: sin cabecera de
// protocolo todavía, cualquier payload recibido se escribe directo al ring
// buffer. El protocolo START/AUDIO/END/PING llega en el Hito 3.
esp_err_t udp_audio_server_start(ring_buffer_t *rb);
