#include "udp_audio_server.h"
#include "protocol.h"
#include "opus_decoder_wrapper.h"
#include "led_ring.h"

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <string.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// Frames Opus perdidos consecutivos a rellenar vía PLC ante un hueco de
// secuencia. Un hueco mayor (p.ej. un START mal numerado) no dispara un
// bucle desmedido de llamadas a PLC.
#define MAX_PLC_FRAMES_PER_GAP (25) // 25 * 20ms = 500ms

// Estadísticas de CPU del decodificador, logueadas cada ~5s.
static int64_t s_decode_time_us_accum = 0;
static uint32_t s_decode_count = 0;
static int64_t s_last_decode_log_ms = 0;

static const char *TAG = "udp_audio_server";

// El decodificador Opus (celt/silk) usa varios KB de pila propios; 4096
// bytes bastaban para el PCM crudo del Hito 1-3 pero desbordaban al añadir
// Opus en el Hito 4 (comprobado en hardware: "stack overflow in task udp_rx").
#define RX_TASK_STACK (10240)
#define RX_TASK_PRIO  (10)
#define RX_TASK_CORE  (0)
#define RX_BUF_SIZE   (1472) // por debajo del MTU típico de WiFi (evita fragmentación IP)

static volatile int64_t s_last_message_time_ms = 0;
static volatile bool s_streaming = false;
static bool s_has_expected_seq = false;
static uint32_t s_expected_seq = 0;
static volatile uint32_t s_lost_packets = 0;

typedef struct {
    ring_buffer_t *rb;
} udp_rx_ctx_t;

static uint32_t read_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static uint16_t read_be16(const uint8_t *p)
{
    return ((uint16_t)p[0] << 8) | p[1];
}

static void write_be32(uint8_t *p, uint32_t v)
{
    p[0] = (v >> 24) & 0xFF;
    p[1] = (v >> 16) & 0xFF;
    p[2] = (v >> 8) & 0xFF;
    p[3] = v & 0xFF;
}

static void write_be16(uint8_t *p, uint16_t v)
{
    p[0] = (v >> 8) & 0xFF;
    p[1] = v & 0xFF;
}

static bool parse_header(const uint8_t *buf, int len, audio_packet_header_t *out)
{
    if (len < PROTOCOL_HEADER_SIZE) {
        return false;
    }
    out->magic = read_be32(buf + 0);
    out->version = buf[4];
    out->frame_type = buf[5];
    out->reserved = read_be16(buf + 6);
    out->seq_num = read_be32(buf + 8);
    out->payload_len = read_be32(buf + 12);
    return out->magic == PROTOCOL_MAGIC && out->version == PROTOCOL_VERSION;
}

static void send_pong(int sock, const struct sockaddr_in *dest, socklen_t socklen, uint32_t seq_num)
{
    uint8_t reply[PROTOCOL_HEADER_SIZE];
    write_be32(reply + 0, PROTOCOL_MAGIC);
    reply[4] = PROTOCOL_VERSION;
    reply[5] = FRAME_PONG;
    write_be16(reply + 6, 0);
    write_be32(reply + 8, seq_num);
    write_be32(reply + 12, 0);
    sendto(sock, reply, sizeof(reply), 0, (const struct sockaddr *)dest, socklen);
}

static void handle_packet(int sock, ring_buffer_t *rb, const uint8_t *buf, int len,
                           const struct sockaddr_in *source_addr, socklen_t socklen)
{
    audio_packet_header_t header;
    if (!parse_header(buf, len, &header)) {
        ESP_LOGW(TAG, "Paquete descartado: cabecera inválida (magic/version) o demasiado corto (%d bytes)", len);
        return;
    }

    const uint8_t *payload = buf + PROTOCOL_HEADER_SIZE;
    int payload_len = len - PROTOCOL_HEADER_SIZE;

    switch (header.frame_type) {
    case FRAME_START:
        ring_buffer_reset(rb); // interrumpe cualquier stream en curso: la alarma más reciente prima
        s_expected_seq = header.seq_num + 1;
        s_has_expected_seq = true;
        s_streaming = true;
        s_last_message_time_ms = esp_timer_get_time() / 1000;
        led_ring_start();
        ESP_LOGI(TAG, "Nuevo stream (seq=%u)", (unsigned) header.seq_num);
        break;

    case FRAME_AUDIO: {
        int16_t pcm[OPUS_FRAME_SAMPLES];

        if (s_has_expected_seq && header.seq_num != s_expected_seq) {
            if (header.seq_num > s_expected_seq) {
                uint32_t lost = header.seq_num - s_expected_seq;
                s_lost_packets += lost;
                ESP_LOGW(TAG, "%u paquete(s) perdido(s) (esperado seq=%u, recibido seq=%u), aplicando PLC",
                         (unsigned) lost, (unsigned) s_expected_seq, (unsigned) header.seq_num);
                uint32_t plc_frames = lost > MAX_PLC_FRAMES_PER_GAP ? MAX_PLC_FRAMES_PER_GAP : lost;
                for (uint32_t i = 0; i < plc_frames; i++) {
                    int64_t t0 = esp_timer_get_time();
                    int samples = opus_decoder_wrapper_conceal(pcm);
                    s_decode_time_us_accum += esp_timer_get_time() - t0;
                    s_decode_count++;
                    if (samples > 0) {
                        ring_buffer_write(rb, (const uint8_t *) pcm, (size_t) samples * sizeof(int16_t));
                    }
                }
            } else {
                ESP_LOGW(TAG, "Paquete fuera de orden/duplicado (esperado seq=%u, recibido seq=%u)",
                         (unsigned) s_expected_seq, (unsigned) header.seq_num);
            }
        }
        s_expected_seq = header.seq_num + 1;
        s_has_expected_seq = true;

        if (payload_len > 0) {
            int64_t t0 = esp_timer_get_time();
            int samples = opus_decoder_wrapper_decode(payload, payload_len, pcm);
            s_decode_time_us_accum += esp_timer_get_time() - t0;
            s_decode_count++;
            if (samples > 0) {
                ring_buffer_write(rb, (const uint8_t *) pcm, (size_t) samples * sizeof(int16_t));
            } else {
                ESP_LOGW(TAG, "Fallo al decodificar frame Opus (seq=%u): %d", (unsigned) header.seq_num, samples);
            }
        }
        s_last_message_time_ms = esp_timer_get_time() / 1000;

        int64_t now_ms = esp_timer_get_time() / 1000;
        if (s_decode_count > 0 && now_ms - s_last_decode_log_ms > 5000) {
            double avg_us = (double) s_decode_time_us_accum / s_decode_count;
            double cpu_pct = (avg_us / 20000.0) * 100.0; // frame de 20ms
            ESP_LOGI(TAG, "Opus decode: %.0fus/frame de media (%.1f%% de un frame de 20ms), %u frames",
                     avg_us, cpu_pct, (unsigned) s_decode_count);
            s_decode_time_us_accum = 0;
            s_decode_count = 0;
            s_last_decode_log_ms = now_ms;
        }
        break;
    }

    case FRAME_END:
        s_streaming = false;
        led_ring_stop();
        ESP_LOGI(TAG, "Fin de stream (seq=%u)", (unsigned) header.seq_num);
        break;

    case FRAME_PING:
        send_pong(sock, source_addr, socklen, header.seq_num);
        break;

    case FRAME_PONG:
        break; // el firmware nunca debería recibir esto; se ignora

    default:
        ESP_LOGW(TAG, "Tipo de frame desconocido: %u", header.frame_type);
        break;
    }
}

static void udp_rx_task(void *arg)
{
    udp_rx_ctx_t *ctx = (udp_rx_ctx_t *) arg;
    uint8_t *rx_buffer = malloc(RX_BUF_SIZE);

    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (sock < 0) {
        ESP_LOGE(TAG, "No se pudo crear el socket UDP: errno %d", errno);
        vTaskDelete(NULL);
        return;
    }

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_addr.s_addr = htonl(INADDR_ANY),
        .sin_port = htons(UDP_AUDIO_SERVER_PORT),
    };
    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "bind() falló: errno %d", errno);
        close(sock);
        vTaskDelete(NULL);
        return;
    }
    ESP_LOGI(TAG, "Escuchando UDP en puerto %d", UDP_AUDIO_SERVER_PORT);

    while (1) {
        struct sockaddr_in source_addr;
        socklen_t socklen = sizeof(source_addr);
        int len = recvfrom(sock, rx_buffer, RX_BUF_SIZE, 0, (struct sockaddr *)&source_addr, &socklen);
        if (len < 0) {
            ESP_LOGE(TAG, "recvfrom() falló: errno %d", errno);
            continue;
        }
        handle_packet(sock, ctx->rb, rx_buffer, len, &source_addr, socklen);
    }
}

esp_err_t udp_audio_server_start(ring_buffer_t *rb)
{
    static udp_rx_ctx_t ctx; // vive durante toda la ejecución del firmware
    ctx.rb = rb;
    BaseType_t ok = xTaskCreatePinnedToCore(udp_rx_task, "udp_rx", RX_TASK_STACK,
                                             &ctx, RX_TASK_PRIO, NULL, RX_TASK_CORE);
    return ok == pdPASS ? ESP_OK : ESP_FAIL;
}

int64_t udp_audio_server_get_last_message_time_ms(void)
{
    return s_last_message_time_ms;
}

bool udp_audio_server_is_streaming(void)
{
    return s_streaming;
}

uint32_t udp_audio_server_get_lost_packets(void)
{
    return s_lost_packets;
}
