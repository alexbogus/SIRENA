# SIRENA
SIRENA (Sistema IP de reconocimiento y envio de nuevas alertas)

<img width="770" height="402" alt="image" src="https://github.com/user-attachments/assets/1cdea14a-07d3-47cc-8268-48d56d397195" />

Gestión de altavoces ESP32-S3 (Waveshare ESP32-S3-AUDIO-Board) para usarlos como megafonía IP en BRAVO 2.

- `esp32s3-firmware/ip-speaker/` — firmware ESP-IDF de cada altavoz (WiFi, protocolo UDP propio, Opus, portal de configuración).
- `docker/dashboard/` — el centro de mando SIRENA: gestión de altavoces/zonas, envío manual de mensajes (TTS con Piper) y reglas de alerta automática sobre el feed 112CV.
- `documentation/` — ver [documentation/README.md](documentation/README.md) para el índice completo (arquitectura, protocolo UDP, API HTTP, setup del entorno).
