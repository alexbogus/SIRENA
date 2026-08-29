#pragma once

// Pines reales de la Waveshare ESP32-S3-AUDIO-Board.
// Fuente: docs/hardware_pins.md (extraído del ejemplo oficial factory_01).
// NO modificar sin volver a contrastar contra el ejemplo oficial.

#include "driver/gpio.h"

// I2C compartido: ES8311 (DAC), TCA9555 (expansor de I/O)
#define BOARD_I2C_PORT      (0)
#define BOARD_I2C_SDA_GPIO  (GPIO_NUM_11)
#define BOARD_I2C_SCL_GPIO  (GPIO_NUM_10)
#define BOARD_I2C_CLOCK_HZ  (100000)

// I2S hacia el ES8311 (reproducción). DIN no se usa (ES7210/micrófono, fuera de alcance).
#define BOARD_I2S_MCLK_GPIO (GPIO_NUM_12)
#define BOARD_I2S_BCLK_GPIO (GPIO_NUM_13)
#define BOARD_I2S_WS_GPIO   (GPIO_NUM_14)
#define BOARD_I2S_DOUT_GPIO (GPIO_NUM_16)

// TCA9555 (expansor de I/O), dirección 0x20 (A0=A1=A2=GND)
#define BOARD_TCA9555_I2C_ADDR (0x20)

// PA_CTRL vive en el TCA9555, EXIO08 (IO_EXPANDER_PIN_NUM_8), no es un GPIO directo del ESP32-S3.
// Ver esp_io_expander.h del componente espressif/esp_io_expander_tca95xx_16bit.

// Botón BOOT nativo (no pasa por el TCA9555)
#define BOARD_BOOT_BUTTON_GPIO (GPIO_NUM_0)

// Anillo de 7 LEDs WS2812 (RGB direccionables)
#define BOARD_LED_STRIP_GPIO      (GPIO_NUM_38)
#define BOARD_LED_STRIP_LED_COUNT (7)
