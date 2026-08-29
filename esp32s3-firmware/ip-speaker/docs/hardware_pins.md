# Pines reales — Waveshare ESP32-S3-AUDIO-Board

Fuente: paquete oficial `ESP32-S3-AUDIO-Board-Demo.zip` descargado desde
`https://files.waveshare.com/wiki/ESP32-S3-AUDIO-Board/ESP32-S3-AUDIO-Board-Demo.zip`
(enlazado desde `docs.waveshare.com/ESP32-S3-AUDIO-Board/Resources-And-Documents`),
proyecto de ejemplo `ESP-IDF/factory_01`.

Archivos fuente citados:
- `factory_01/main/hardeware_driver/bsp_board.h`
- `factory_01/main/tca9555_driver/tca9555_driver.c`
- `factory_01/main/audio_play_driver/audio_driver.c`
- `factory_01/main/button_driver/button_driver.c`

## I2C (bus compartido: ES8311, ES7210, TCA9555)

| Señal | GPIO |
|---|---|
| SDA | `GPIO_NUM_11` |
| SCL | `GPIO_NUM_10` |
| Bus I2C | `I2C_NUM_0` |

## I2S (hacia/desde los codecs ES8311 DAC / ES7210 ADC)

| Señal | GPIO | Uso |
|---|---|---|
| MCLK | `GPIO_NUM_12` | Master clock |
| BCLK (SCLK) | `GPIO_NUM_13` | Bit clock |
| WS (LRCK) | `GPIO_NUM_14` | Word select / L-R clock |
| DOUT | `GPIO_NUM_16` | ESP32 → ES8311 (reproducción, lo que usaremos) |
| DIN (SDIN) | `GPIO_NUM_15` | ES7210 → ESP32 (micrófono, no se usa en este proyecto) |

Configuración de referencia en el ejemplo oficial: formato Philips estándar,
32 bits por canal, estéreo (`I2S_SLOT_MODE_STEREO`), 16000 Hz.

## Expansor de I/O TCA9555 (dirección I2C `ESP_IO_EXPANDER_I2C_TCA9555_ADDRESS_000` = `0x20`)

| Pin (EXIO) | Dirección | Uso confirmado en el ejemplo oficial |
|---|---|---|
| `IO_EXPANDER_PIN_NUM_8` | Salida | **`PA_CTRL`** — habilita el amplificador de audio (`Audio_PA_EN()` en `audio_driver.c`, pone el pin a `true` antes de reproducir/grabar) |
| `IO_EXPANDER_PIN_NUM_0`, `_1`, `_5`, `_6` | Salida | Otros usos del ejemplo (LCD/periféricos), no relevantes para este proyecto |
| `IO_EXPANDER_PIN_NUM_9`, `_10`, `_11` | Entrada | 3 botones físicos de la placa, leídos por `button_driver.c` vía `esp_io_expander_get_level` (activos a nivel bajo) |
| `IO_EXPANDER_PIN_NUM_2` | Entrada | Reservado en el ejemplo (probablemente interrupción de touch LCD), no relevante aquí |

**Importante:** `PA_CTRL` NO es un GPIO directo del ESP32-S3, cuelga del TCA9555. Para
activar el amplificador antes de reproducir audio hay que:
1. Inicializar el TCA9555 vía `esp_io_expander_new_i2c_tca95xx_16bit()` sobre el bus I2C anterior.
2. Configurar `IO_EXPANDER_PIN_NUM_8` como salida.
3. Poner `IO_EXPANDER_PIN_NUM_8` a nivel alto (`true`) antes de escribir al I2S, y opcionalmente
   a bajo cuando no haya reproducción, para ahorrar energía / evitar pops.

## WS2812 (anillo de 7 LEDs RGB)

| Señal | GPIO |
|---|---|
| Data | `GPIO_NUM_38` (`LED_STRIP_GPIO_PIN`), `LED_STRIP_LED_COUNT = 7` |

No se usa en este proyecto (megafonía sin interfaz visual), documentado por completitud
y para evitar colisiones futuras.

## Botones

| Botón | Vía |
|---|---|
| BOOT | GPIO0 nativo del ESP32-S3 (estándar en toda la familia, no pasa por el TCA9555) |
| RESET | Línea EN nativa, no es un GPIO controlable por software |
| 3 botones de usuario | TCA9555 `EXIO09` / `EXIO10` / `EXIO11` (ver tabla del expansor arriba) |

## No usado en este proyecto (documentado para evitar colisiones)

- SD card (SDMMC): `GPIO_NUM_40` (CLK), `GPIO_NUM_42` (CMD), `GPIO_NUM_41` (D0)
- LCD: `GPIO_NUM_5` (SCLK), `GPIO_NUM_1` (MOSI), `GPIO_NUM_3` (DC), `GPIO_NUM_6` (CS)
- Touch LCD interrupt: `GPIO_NUM_9`

## Notas

- El ejemplo oficial usa la librería `esp_codec_dev` (component de Espressif) para
  abstraer el códec ES8311 en vez de escribir registros I2C a mano. Evaluar si
  este proyecto reutiliza `esp_codec_dev` (menos código propio, ya probado) o
  implementa un driver ES8311 mínimo propio (más control fino, más código a mantener)
  — a decidir en el Hito 1 al implementar `audio_codec_es8311.c`.
- El volumen de reproducción del ejemplo oficial (`PLAYER_VOLUME = 60`) se gestiona
  vía `esp_audio_set_play_vol()` / `esp_audio_get_play_vol()` de `esp_codec_dev`,
  relevante para el diseño de `POST /volume` del Hito 2.
