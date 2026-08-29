#pragma once

#include <stdint.h>

// Protocolo UDP propio para delimitar streams de audio y detectar pérdida de
// paquetes. Cabecera de 16 bytes en network byte order, seguida del payload
// (PCM en el Hito 3, frames Opus a partir del Hito 4).
//
// Se parsea/serializa campo a campo (ntohl/ntohs, htonl/htons) en vez de
// castear el buffer recibido a este struct, para no depender de la
// alineación de memoria del compilador.
//
// Referencia Python (lado Docker): docker/reference_send_audio.py

#define PROTOCOL_MAGIC (0x53504B31u) // "SPK1"
#define PROTOCOL_VERSION (1)
#define PROTOCOL_HEADER_SIZE (16)

typedef enum {
    FRAME_START = 1, // Inicia un stream nuevo. Interrumpe cualquier stream en curso.
    FRAME_AUDIO = 2, // payload = bloque de audio (PCM en Hito 3, Opus en Hito 4)
    FRAME_END = 3,   // Fin del stream. El buffer se deja drenar de forma natural.
    FRAME_PING = 4,  // Health-check de red; el firmware responde con PONG.
    FRAME_PONG = 5,  // Respuesta a PING (el firmware nunca la recibe, solo la envía).
} frame_type_t;

typedef struct {
    uint32_t magic;       // debe ser PROTOCOL_MAGIC
    uint8_t version;      // PROTOCOL_VERSION
    uint8_t frame_type;   // frame_type_t
    uint16_t reserved;    // sin uso, reservado para futuros flags
    uint32_t seq_num;     // incremental dentro del stream, para detectar huecos
    uint32_t payload_len; // bytes que siguen a la cabecera
} audio_packet_header_t;
