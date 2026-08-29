#pragma once

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

// Envoltorio mínimo sobre libopus (componente 78/esp-opus) para decodificar
// frames de 20ms a 16kHz mono, con soporte de PLC (Packet Loss Concealment)
// para frames perdidos.
#define OPUS_FRAME_SAMPLES (320) // 20ms a 16kHz

esp_err_t opus_decoder_wrapper_init(void);

// Decodifica un frame Opus recibido. Devuelve el número de muestras
// decodificadas (debería ser OPUS_FRAME_SAMPLES) o negativo en error.
// `pcm_out` debe tener espacio para OPUS_FRAME_SAMPLES muestras int16.
int opus_decoder_wrapper_decode(const uint8_t *data, int len, int16_t *pcm_out);

// Genera audio de relleno (PLC) para un frame perdido, sin datos de entrada.
// Devuelve el número de muestras generadas o negativo en error.
int opus_decoder_wrapper_conceal(int16_t *pcm_out);
