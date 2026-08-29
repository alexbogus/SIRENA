#pragma once

#include "esp_err.h"
#include "ring_buffer.h"
#include <stdint.h>

#define UDP_AUDIO_SERVER_PORT (5005)

// Arranca la tarea de recepción UDP (core 0). Hito 1: sin cabecera de
// protocolo todavía, cualquier payload recibido se escribe directo al ring
// buffer. El protocolo START/AUDIO/END/PING llega en el Hito 3.
esp_err_t udp_audio_server_start(ring_buffer_t *rb);

// Milisegundos (esp_timer_get_time()/1000) del último paquete recibido, o 0
// si no se ha recibido ninguno desde el arranque.
int64_t udp_audio_server_get_last_message_time_ms(void);
