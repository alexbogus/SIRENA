#include "ring_buffer.h"
#include <string.h>
#include "esp_heap_caps.h"

esp_err_t ring_buffer_init(ring_buffer_t *rb, size_t capacity)
{
    memset(rb, 0, sizeof(*rb));
    rb->buffer = heap_caps_malloc(capacity, MALLOC_CAP_SPIRAM);
    if (rb->buffer == NULL) {
        return ESP_ERR_NO_MEM;
    }
    rb->capacity = capacity;
    return ESP_OK;
}

void ring_buffer_reset(ring_buffer_t *rb)
{
    // Solo lo llama el productor (udp_rx_task) al procesar un nuevo START;
    // mover tail junto con head es seguro porque el consumidor solo lee
    // ring_buffer_bytes_available() en cada iteración, nunca asume monotonicidad.
    rb->tail = rb->head;
}

size_t ring_buffer_bytes_available(const ring_buffer_t *rb)
{
    size_t head = rb->head;
    size_t tail = rb->tail;
    return head - tail; // aritmética modular sobre size_t, correcta con wraparound
}

size_t ring_buffer_free_space(const ring_buffer_t *rb)
{
    return rb->capacity - ring_buffer_bytes_available(rb);
}

size_t ring_buffer_write(ring_buffer_t *rb, const uint8_t *data, size_t len)
{
    size_t free_space = ring_buffer_free_space(rb);
    if (len > free_space) {
        rb->overrun_count++;
        len = free_space; // se descarta lo que no cabe (los bytes más nuevos)
    }
    for (size_t i = 0; i < len; i++) {
        rb->buffer[(rb->head + i) % rb->capacity] = data[i];
    }
    rb->head += len;
    return len;
}

size_t ring_buffer_read_or_silence(ring_buffer_t *rb, uint8_t *out, size_t len)
{
    size_t available = ring_buffer_bytes_available(rb);
    size_t to_read = available < len ? available : len;
    if (to_read < len) {
        rb->underrun_count++;
    }
    for (size_t i = 0; i < to_read; i++) {
        out[i] = rb->buffer[(rb->tail + i) % rb->capacity];
    }
    if (to_read < len) {
        memset(out + to_read, 0, len - to_read); // relleno de silencio
    }
    rb->tail += to_read;
    return len;
}
