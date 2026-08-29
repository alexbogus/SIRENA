# Documentación — esp32s3-ip-speaker-net

Gestión de altavoces ESP32-S3 (Waveshare ESP32-S3-AUDIO-Board) usados como megafonía IP en BRAVO 2. Un servicio Docker (aún por construir) recibe JSON de alarmas, genera voz con Piper TTS y la envía en tiempo real por UDP al altavoz de la zona/población correspondiente.

## Índice

- [setup.md](setup.md) — instalación del entorno ESP-IDF, identificación del puerto serie y primer flasheo.
- [architecture.md](architecture.md) — arquitectura del firmware: componentes, tareas FreeRTOS, ring buffer, flujo de audio.
- [protocolo-udp.md](protocolo-udp.md) — especificación del protocolo UDP propio (cabecera, tipos de frame, ejemplo en Python).
- [api-http.md](api-http.md) — endpoints HTTP de status/control y el portal de configuración WiFi.
- [../esp32s3-firmware/ip-speaker/docs/hardware_pins.md](../esp32s3-firmware/ip-speaker/docs/hardware_pins.md) — pinout real de la placa, extraído del ejemplo oficial de Waveshare (no inventado).

## Estado del proyecto

Los 6 hitos de la primera versión del firmware están completos y validados en hardware real (issues [#1](https://github.com/alexbogus/esp32s3-ip-speaker-net/issues/1)–[#6](https://github.com/alexbogus/esp32s3-ip-speaker-net/issues/6) del repositorio, todos cerrados):

| Hito | Contenido |
|---|---|
| 0 | Pines reales del hardware (extraídos del ejemplo oficial `factory_01`) |
| 1 | WiFi + UDP + PCM crudo audible (MVP de audio) |
| 2 | API HTTP de status y control (`GET /status`, `POST /volume`) |
| 3 | Protocolo UDP con cabecera (`START`/`AUDIO`/`END`/`PING`/`PONG`) |
| 4 | Integración de Opus (decodificación + PLC ante pérdida de paquetes) |
| 5 | Portal de configuración WiFi/IP en modo AP + persistencia en NVS |

Pendiente (fuera del alcance de este firmware): el servicio Docker que recibe las alarmas, genera la voz con Piper y las envía a los altavoces — ver `docker/reference_send_audio.py` como punto de partida del protocolo de envío.

## Quick start

```bash
source /Users/alexcasanova/.espressif/tools/activate_idf_v6.1.sh
cd esp32s3-firmware/ip-speaker
cp main/wifi_credentials.h.example main/wifi_credentials.h  # y rellena tu SSID/password
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

Para enviarle audio de prueba desde un Mac/Linux con Python:
```bash
pip install opuslib   # + libopus del sistema (brew install opus / apt install libopus0)
python3 docker/reference_send_audio.py --host <IP_DEL_ALTAVOZ> --wav audio_16k_mono.wav
```
