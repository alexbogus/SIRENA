# SIRENA
SIRENA (Sistema IP de reconocimiento y envio de nuevas alertas)

<img width="1669" height="962" alt="image" src="https://github.com/user-attachments/assets/465955fb-8055-42e8-b9bb-832726deb81f" />


Gestión de altavoces ESP32-S3 (Waveshare ESP32-S3-AUDIO-Board) para usarlos como megafonía IP en BRAVO 2.

- `esp32s3-firmware/ip-speaker/` — firmware ESP-IDF de cada altavoz (WiFi, protocolo UDP propio, Opus, portal de configuración).
- `docker/dashboard/` — el centro de mando SIRENA: gestión de altavoces/zonas, envío manual de mensajes (TTS con Piper) y reglas de alerta automática sobre el feed 112CV.
- `docker/reference_send_audio.py` — implementación de referencia del protocolo de envío de audio (empaquetado de cabecera, codificación Opus, pacing), usada por `docker/dashboard/services/sender.py`.
- `documentation/` — ver [documentation/README.md](documentation/README.md) para el índice completo (arquitectura, protocolo UDP, API HTTP, setup del entorno).

Para el historial de cambios del proyecto (firmware y dashboard), ver [CHANGELOG.md](CHANGELOG.md).

## Backups y recuperación (dashboard)

Solo se respalda la base de datos (`docker/data/dashboard.db`): reglas, zonas, altavoces, historial de mensajes y deduplicación de incidentes 112CV. Logs y modelos de voz/tonos quedan fuera deliberadamente (recreables, no críticos).

- **Automático:** `docker/update.sh` crea una copia (vía `sqlite3 .backup`, segura aunque la BD esté en uso) al principio de cada ejecución, antes de tocar nada — instala `sqlite3` con `apt` si hace falta, y si no puede garantizar el backup **aborta la actualización** en vez de desplegar sin red de seguridad. Las copias se guardan en `docker/backups/dashboard_AAAAMMDD_HHMMSS.db`, con una retención de `BACKUP_RETENTION_DAYS` días (30 por defecto) — no solo se guarda la última.
- **Manual, desde la propia app:** en `/settings → Copias de seguridad` se puede crear una copia bajo demanda, restaurar cualquiera de las existentes, o restaurar subiendo un `.db` externo. El archivo se valida (cabecera SQLite + tablas esperadas) antes de aplicarlo; restaurar hace antes una copia del estado actual (el restore es en sí mismo reversible) y reinicia la aplicación (unos segundos de corte) para que relea la base de datos desde cero.
- **Restaurar a mano en el VPS** (si la app no arranca): con el contenedor parado, copiar el `.db` elegido de `docker/backups/` sobre `docker/data/dashboard.db` y levantar de nuevo con `docker compose up -d`.
