#pragma once

#include "esp_err.h"
#include "ring_buffer.h"
#include <stdint.h>
#include <stdbool.h>

#define UDP_AUDIO_SERVER_PORT (5005)

// Arranca la tarea de recepción UDP (core 0). Parsea la cabecera del
// protocolo (protocol.h) y gestiona la máquina de estados
// START/AUDIO/END/PING.
esp_err_t udp_audio_server_start(ring_buffer_t *rb);

// Milisegundos (esp_timer_get_time()/1000) del último paquete AUDIO/START
// recibido, o 0 si no se ha recibido ninguno desde el arranque.
int64_t udp_audio_server_get_last_message_time_ms(void);

// true si hay un stream activo (entre START y END). Refleja el estado real
// del protocolo, no una estimación por ocupación del ring buffer.
bool udp_audio_server_is_streaming(void);

// Contadores para diagnóstico (expuestos también en GET /status si hiciera falta).
uint32_t udp_audio_server_get_lost_packets(void);
