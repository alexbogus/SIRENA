#include "led_ring.h"
#include "board_pins.h"

#include "led_strip.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

static const char *TAG = "led_ring";

// "Cometa": una cabeza a brillo pleno y una cola de este tamaño con brillo
// decreciente, girando alrededor del anillo. TAIL_LEN < LED_COUNT para que
// siempre haya al menos un LED apagado y se perciba el giro.
#define TAIL_LEN       (3)
#define STEP_DELAY_MS  (45) // ~315ms por vuelta completa (7 LEDs), ritmo tipo "spinner"

// Azul tipo Alexa.
#define HEAD_R (0)
#define HEAD_G (120)
#define HEAD_B (255)

static led_strip_handle_t s_strip;
static volatile bool s_active = false;
static SemaphoreHandle_t s_wake_sem;

static void render_step(int head_pos)
{
    for (int i = 0; i < BOARD_LED_STRIP_LED_COUNT; i++) {
        // distancia (hacia atrás) desde la cabeza, con wrap-around
        int dist = head_pos - i;
        if (dist < 0) {
            dist += BOARD_LED_STRIP_LED_COUNT;
        }
        if (dist > TAIL_LEN) {
            led_strip_set_pixel(s_strip, i, 0, 0, 0);
            continue;
        }
        // brillo 100% en la cabeza, decreciente linealmente hacia la cola
        uint32_t scale_pct = 100 - (dist * 100 / (TAIL_LEN + 1));
        led_strip_set_pixel(s_strip, i, (HEAD_R * scale_pct) / 100,
                             (HEAD_G * scale_pct) / 100, (HEAD_B * scale_pct) / 100);
    }
    led_strip_refresh(s_strip);
}

static void led_ring_task(void *arg)
{
    int head_pos = 0;
    while (1) {
        if (!s_active) {
            led_strip_clear(s_strip);
            // bloquea hasta que led_ring_start() nos despierte
            xSemaphoreTake(s_wake_sem, portMAX_DELAY);
            head_pos = 0;
            continue;
        }
        render_step(head_pos);
        head_pos = (head_pos + 1) % BOARD_LED_STRIP_LED_COUNT;
        vTaskDelay(pdMS_TO_TICKS(STEP_DELAY_MS));
    }
}

esp_err_t led_ring_init(void)
{
    led_strip_config_t strip_config = {
        .strip_gpio_num = BOARD_LED_STRIP_GPIO,
        .max_leds = BOARD_LED_STRIP_LED_COUNT,
        .led_model = LED_MODEL_WS2812,
        // El anillo de esta placa resultó ser RGB, no el GRB estándar de
        // WS2812 (con GRB el rojo salía verde) -- confirmado visualmente en
        // hardware real.
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_RGB,
    };
    led_strip_rmt_config_t rmt_config = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,
        .flags.with_dma = false,
    };
    esp_err_t err = led_strip_new_rmt_device(&strip_config, &rmt_config, &s_strip);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "led_strip_new_rmt_device falló: %s", esp_err_to_name(err));
        return err;
    }
    led_strip_clear(s_strip);

    s_wake_sem = xSemaphoreCreateBinary();
    if (s_wake_sem == NULL) {
        return ESP_ERR_NO_MEM;
    }

    // Prioridad baja y sin anclar a un core: no debe competir con udp_rx
    // (core 0, prio 10) ni con i2s_player (core 1) por CPU en tiempo real.
    BaseType_t ok = xTaskCreate(led_ring_task, "led_ring", 2048, NULL, 3, NULL);
    if (ok != pdPASS) {
        ESP_LOGE(TAG, "No se pudo crear la tarea led_ring");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Anillo de %d LEDs listo (GPIO%d)", BOARD_LED_STRIP_LED_COUNT, BOARD_LED_STRIP_GPIO);
    return ESP_OK;
}

void led_ring_start(void)
{
    s_active = true;
    xSemaphoreGive(s_wake_sem); // no-op si la tarea ya está activa (no bloqueada)
}

void led_ring_stop(void)
{
    s_active = false;
}
