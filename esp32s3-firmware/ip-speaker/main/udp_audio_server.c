#include "udp_audio_server.h"

#include <sys/socket.h>
#include <netinet/in.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "udp_audio_server";

#define RX_TASK_STACK (4096)
#define RX_TASK_PRIO  (10)
#define RX_TASK_CORE  (0)
#define RX_BUF_SIZE   (1472) // por debajo del MTU típico de WiFi (evita fragmentación IP)

typedef struct {
    ring_buffer_t *rb;
} udp_rx_ctx_t;

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
        ring_buffer_write(ctx->rb, rx_buffer, (size_t) len);
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
