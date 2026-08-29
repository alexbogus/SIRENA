#pragma once

#include "esp_err.h"
#include "ring_buffer.h"

// Arranca la tarea de reproducción (core 1) que consume el ring buffer dado
// y lo escribe al codec (audio_codec_write). Ante underrun escribe silencio
// en vez de bloquear, para no cortar el reloj I2S.
esp_err_t i2s_player_start(ring_buffer_t *rb);

// Autoprueba: genera un tono seno de `freq_hz` durante `duration_ms` y lo
// escribe directamente al codec, sin pasar por el ring buffer ni la red.
// Sirve para aislar problemas de audio/I2S de problemas de red (Hito 1).
esp_err_t i2s_player_play_test_tone(int freq_hz, int duration_ms);
