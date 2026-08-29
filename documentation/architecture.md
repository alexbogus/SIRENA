# Arquitectura del firmware

Proyecto ESP-IDF en `esp32s3-firmware/ip-speaker/`, todo el código en `main/`. Orquestado desde `main/ip-speaker.c` (`app_main()`).

## Hardware

Waveshare ESP32-S3-AUDIO-Board: ESP32-S3R8 (240MHz dual-core, 8MB PSRAM **Octal**, 16MB flash), codec **ES8311** (DAC/altavoz, el que usamos), **ES7210** (ADC/micrófono, no usado), amplificador controlado por un expansor de I/O **TCA9555** en el bus I2C compartido. Pinout real (no inventado, extraído del ejemplo oficial `factory_01` de Waveshare) en [`../esp32s3-firmware/ip-speaker/docs/hardware_pins.md`](../esp32s3-firmware/ip-speaker/docs/hardware_pins.md).

Detalle importante: `PA_CTRL` (habilita el amplificador) es el pin `EXIO08` del TCA9555, **no** un GPIO directo del ESP32-S3.

## Flujo de arranque (`app_main`)

1. **`audio_codec_es8311_init()`** — inicializa el bus I2C compartido, el TCA9555 (deja `PA_CTRL` a bajo por defecto), el canal I2S TX (16kHz/mono/16-bit), y el codec ES8311 vía el componente `esp_codec_dev` (no el componente standalone `espressif/es8311`, que usa el driver I2C legacy y entraría en conflicto con el driver moderno `i2c_master` que usa el TCA9555 en el mismo bus).
2. Se reproduce un tono de prueba (440Hz, 1s) como autoprueba del pipeline de audio, aislado de la red.
3. Se reserva el **ring buffer** (64KB en PSRAM) y se inicializa el decodificador Opus.
4. **`wifi_manager_start()`** — ver [flujo de arranque de red](#wifi-y-modo-de-configuración) más abajo.
5. Si hay conexión WiFi: sincroniza hora por SNTP, carga el volumen persistido, activa el amplificador, y arranca las tareas de reproducción (`i2s_player_start`), recepción UDP (`udp_audio_server_start`) y el servidor HTTP de status (`http_status_server_start`).
6. Si no hay conexión WiFi (modo AP de configuración): solo arranca el portal de configuración y `app_main` termina (las demás tareas no tienen sentido en la red aislada del AP).

## WiFi y modo de configuración

`wifi_manager` intenta conectar en modo STA con, por este orden de prioridad:
1. Credenciales guardadas en NVS (namespace `ipspk_cfg`, ver `nvs_config.c`), guardadas por el portal de configuración.
2. Credenciales compiladas en `main/wifi_credentials.h` (solo como fallback de desarrollo; no se sube a git).

Si no hay credenciales válidas, si la conexión falla tras el timeout, o si el **botón BOOT** (GPIO0) se mantiene pulsado en el arranque, se levanta un **AP abierto** `IPSpeaker-Config-XXXX` (XXXX = sufijo de la MAC) sirviendo un formulario HTTP mínimo (`http_config_server.c`) en `http://192.168.4.1/`. Al enviarlo, se guarda en NVS y el dispositivo se reinicia para aplicar la nueva configuración.

Tras conectar, siempre se llama a `esp_wifi_set_ps(WIFI_PS_NONE)`: el ahorro de energía WiFi por defecto introduce jitter variable en la recepción UDP (audible como cortes), así que se desactiva para audio en tiempo real.

**Importante**: en modo AP de configuración **no** se arranca también `http_status_server` — ambos intentarían escuchar en el puerto 80 y `httpd_start()` fallaría (esto causó un `abort()` real durante el desarrollo del Hito 5, ver commit `41943f0`).

## Pipeline de audio

```
[udp_rx_task, core 0]              [i2s_playback_task, core 1]
  recvfrom() UDP                     lee bloques de 640 bytes
    → parsea cabecera del protocolo    del ring buffer
    → decodifica Opus (o PLC            → audio_codec_write()
      si hay hueco de secuencia)          (I2S → ES8311 → altavoz)
    → ring_buffer_write()
```

- **`ring_buffer`**: buffer circular de bytes **SPSC lock-free** (single-producer/single-consumer, sin mutex) reservado en PSRAM, 64KB (~2s de margen a 16kHz/mono/16-bit). Un único productor (`udp_rx_task`) y un único consumidor (`i2s_playback_task`) hacen innecesario un mutex, y evitan inversión de prioridad entre una tarea de red de prioridad más baja y una de audio de prioridad más alta.
- **`udp_audio_server`**: parsea la cabecera del protocolo (ver [protocolo-udp.md](protocolo-udp.md)), gestiona la máquina de estados `START`/`AUDIO`/`END`/`PING`, detecta huecos de secuencia (paquetes perdidos) y decodifica cada frame `AUDIO` con `opus_decoder_wrapper` antes de escribirlo al ring buffer. Un `START` nuevo interrumpe inmediatamente cualquier stream en curso (`ring_buffer_reset`) — la alarma más reciente siempre prima. Ante un hueco de secuencia, se generan hasta 25 frames de relleno vía **PLC** (Packet Loss Concealment) de Opus en vez de silencio.
- **`i2s_player`**: tarea de reproducción en el core 1, lee bloques fijos de 640 bytes (20ms) del ring buffer y los escribe al codec; si no hay suficientes datos (underrun), rellena con silencio en vez de bloquear, para no cortar el reloj I2S.
- **`opus_decoder_wrapper`**: envoltorio sobre `78/esp-opus` (libopus), frames de 20ms/320 muestras a 16kHz mono. Coste medido en hardware: **~8% de CPU de un core por frame de 20ms**.

## API HTTP y persistencia

Ver [api-http.md](api-http.md) para el detalle de `GET /status`, `POST /volume` y el portal de configuración.

- `http_status_server` (solo en modo STA) expone el estado operativo real del altavoz (`udp_audio_server_is_streaming()`, no una estimación por ocupación del buffer).
- `time_sync` sincroniza la hora vía SNTP (`pool.ntp.org`, zona horaria Europe/Madrid) para poder reportar timestamps legibles.
- `nvs_config` y `volume_storage` persisten en NVS (namespace `ipspk_cfg`): credenciales WiFi, IP estática opcional, `speaker_id`, y el volumen actual (0-100%, registro de ganancia del ES8311).

## Gotchas conocidos (encontrados y corregidos durante el desarrollo)

- **Stack overflow en `udp_rx_task`**: el estado interno de Opus (celt/silk) necesita varios KB de pila. 4KB bastaban para PCM crudo (Hito 1-3) pero provocaban un reinicio silencioso al añadir Opus (Hito 4). Subido a 10KB.
- **Partición de flash agotada**: la partición "single app" por defecto (1MB) se llenó casi al 100% al enlazar Opus. Se sustituyó por una tabla de particiones a medida (`partitions.csv`) con 4MB de partición app, aprovechando los 16MB de flash reales.
- **PSRAM en modo Quad por defecto**: el chip de esta placa es Octal-SPI; hay que forzar `CONFIG_SPIRAM_MODE_OCT=y` explícitamente en el `sdkconfig` (el valor por defecto de Kconfig es Quad).
- **Microcortes en el emisor**: un emisor que envía cada bloque exactamente al ritmo real-time, sin colchón, produce audio cortado porque cualquier jitter de red hace que el ring buffer se quede momentáneamente vacío. La solución (implementada en `docker/reference_send_audio.py`) es enviar un colchón inicial de ~300ms antes de empezar el ritmo real-time.
