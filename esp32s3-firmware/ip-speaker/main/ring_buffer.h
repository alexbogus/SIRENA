#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"

// Ring buffer de bytes SPSC (single-producer/single-consumer) sin mutex,
// pensado para un único productor (udp_rx_task) y un único consumidor
// (i2s_playback_task). Reservado en PSRAM.
typedef struct {
    uint8_t *buffer;
    size_t capacity;
    volatile size_t head; // solo lo escribe el productor
    volatile size_t tail; // solo lo escribe el consumidor
    volatile uint32_t overrun_count;  // paquetes descartados por buffer lleno
    volatile uint32_t underrun_count; // lecturas que no encontraron suficientes datos
} ring_buffer_t;

// Reserva `capacity` bytes en PSRAM. Devuelve ESP_OK o error.
esp_err_t ring_buffer_init(ring_buffer_t *rb, size_t capacity);

// Vacía el buffer inmediatamente (usado al interrumpir un stream con un nuevo START).
void ring_buffer_reset(ring_buffer_t *rb);

size_t ring_buffer_bytes_available(const ring_buffer_t *rb);
size_t ring_buffer_free_space(const ring_buffer_t *rb);

// Escribe hasta `len` bytes. Si no hay espacio suficiente, escribe lo que quepa
// y cuenta un overrun (nunca bloquea). Devuelve los bytes realmente escritos.
size_t ring_buffer_write(ring_buffer_t *rb, const uint8_t *data, size_t len);

// Lee hasta `len` bytes. Si hay menos disponibles, copia lo que haya y rellena
// el resto con silencio (0x00), contando un underrun. Nunca bloquea.
// Devuelve siempre `len` (el buffer de salida queda siempre completo).
size_t ring_buffer_read_or_silence(ring_buffer_t *rb, uint8_t *out, size_t len);
