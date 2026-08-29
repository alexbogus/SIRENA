#pragma once

#include "esp_err.h"
#include "esp_codec_dev.h"

// Sample rate/canales/bits fijados para el proyecto (Hito 1: PCM crudo 16kHz mono 16-bit).
#define AUDIO_SAMPLE_RATE_HZ (16000)
#define AUDIO_CHANNELS       (1)
#define AUDIO_BITS_PER_SAMPLE (16)

// Inicializa el bus I2C compartido, el expansor TCA9555 (PA_CTRL), el driver I2S
// y el codec ES8311, y abre el dispositivo de reproducción a AUDIO_SAMPLE_RATE_HZ.
// Debe llamarse una única vez, antes de audio_codec_write().
esp_err_t audio_codec_es8311_init(void);

// Escribe PCM intercalado (según AUDIO_CHANNELS/AUDIO_BITS_PER_SAMPLE) al codec. Bloqueante.
esp_err_t audio_codec_write(const void *data, size_t len);

// Activa/desactiva el amplificador de audio (TCA9555 EXIO08).
esp_err_t audio_codec_set_pa_enabled(bool enabled);

// Volumen 0-100. Ajusta el registro de ganancia del ES8311 vía esp_codec_dev.
esp_err_t audio_codec_set_volume(int volume_percent);
esp_err_t audio_codec_get_volume(int *volume_percent);
