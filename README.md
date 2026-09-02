# SIRENA
SIRENA (Sistema IP de reconocimiento y envio de nuevas alertas)

<img width="1669" height="962" alt="image" src="https://github.com/user-attachments/assets/465955fb-8055-42e8-b9bb-832726deb81f" />


Gestión de altavoces ESP32-S3 (Waveshare ESP32-S3-AUDIO-Board) para usarlos como megafonía IP en BRAVO 2.

- `esp32s3-firmware/ip-speaker/` — firmware ESP-IDF de cada altavoz (WiFi, protocolo UDP propio, Opus, portal de configuración).
- `docker/dashboard/` — el centro de mando SIRENA: gestión de altavoces/zonas, envío manual de mensajes (TTS con Piper) y reglas de alerta automática sobre el feed 112CV.
- `docker/reference_send_audio.py` — implementación de referencia del protocolo de envío de audio (empaquetado de cabecera, codificación Opus, pacing), usada por `docker/dashboard/services/sender.py`.
- `documentation/` — ver [documentation/README.md](documentation/README.md) para el índice completo (arquitectura, protocolo UDP, API HTTP, setup del entorno).

Para el historial de cambios del proyecto (firmware y dashboard), ver [CHANGELOG.md](CHANGELOG.md).
