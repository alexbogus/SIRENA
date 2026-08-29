#pragma once

#include "esp_err.h"

// Efecto visual en el anillo de 7 LEDs WS2812 (GPIO38, ver board_pins.h):
// un "cometa" azul (tipo Alexa) gira alrededor del anillo mientras se
// reproduce un mensaje por megafonía, y se apaga cuando termina. Pensado
// como indicador de "hay un audio sonando ahora mismo" para quien esté
// cerca del altavoz, no como interfaz de estados tipo asistente de voz.

esp_err_t led_ring_init(void);

// Arranca el efecto (idempotente: llamar varias veces seguidas no reinicia
// la animación desde cero). Pensado para llamarse en FRAME_START.
void led_ring_start(void);

// Apaga el anillo. Pensado para llamarse en FRAME_END.
void led_ring_stop(void);
