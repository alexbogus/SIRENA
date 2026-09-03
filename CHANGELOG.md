# Changelog

Registro de cambios relevantes del proyecto (firmware `esp32s3-firmware/ip-speaker/` y centro de mando `docker/dashboard/` — SIRENA). Formato inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/), con [SemVer](https://semver.org/lang/es/) aplicado de forma laxa (proyecto interno sin releases publicados: MAJOR para rediseños/rupturas grandes, MINOR para funcionalidad nueva, PATCH para arreglos).

La entrada más reciente (la primera de este archivo) es la que se muestra como versión actual en el pie del sidebar del dashboard — para publicar una versión nueva basta con añadir una sección `## [X.Y.Z] - AAAA-MM-DD` al principio de este archivo.

## [1.5.1] - 2026-09-03

### Cambiado
- Intervalo por defecto de sondeo del feed 112CV subido de 45s a 180s.
- Tarjetas de altavoz: el punto de estado (online/streaming/offline) se sustituye por una barra superior de color, más visible.

### Corregido
- El contenedor `dashboard` corría en UTC (base `python:3.12-slim`) mientras `config.now_sql()` y el JS del dashboard asumen hora local Europe/Madrid, provocando un desfase de 1-2h en timestamps mostrados (p. ej. "última comprobación" del feed 112CV); `docker-compose.yml` fija ahora `TZ=Europe/Madrid`.

## [1.5.0] - 2026-09-02

### Añadido
- Copias de seguridad de la base de datos con política de retención (no solo la última): `docker/update.sh` crea una automáticamente antes de cada despliegue (instala `sqlite3` con `apt` si hace falta; aborta el despliegue si no puede garantizar el backup) y las poda pasados `BACKUP_RETENTION_DAYS` días (30 por defecto).
- `/settings → Copias de seguridad`: crear una copia manual, restaurar cualquiera de las existentes o restaurar subiendo un `.db` externo, con validación del archivo (cabecera SQLite + tablas esperadas) y backup de seguridad automático antes de aplicar cualquier restore.

### Corregido
- Motivado por un incidente real: un cambio de rutas de volúmenes Docker (ver 1.3.1) dejó el dashboard arrancando con una base de datos vacía en producción sin que el healthcheck (solo hace `SELECT 1`) lo detectara, porque `update.sh` nunca movía los datos del host a la ruta nueva. Los backups automáticos + la posibilidad de restaurar desde la propia app evitan que esto vuelva a suponer una pérdida de datos.

## [1.4.0] - 2026-09-02

### Añadido
- El sidebar muestra la versión actual de la app en vez del texto fijo "Protección Civil Godella / Despliegue BRAVO 2"; al pulsarla se abre un modal con este mismo CHANGELOG renderizado, para hacer seguimiento de novedades sin salir del dashboard.

## [1.3.1] - 2026-09-02

### Corregido
- Un tono TTS ausente en disco ya no tumba la alerta completa: `services/tts.py` cae al tono por defecto y loguea un warning en vez de lanzar `FileNotFoundError`.
- Las alertas 112CV que fallaban al anunciarse (tono roto, sin altavoces resueltos) quedaban bloqueadas indefinidamente sin reintentar. Ahora se reintentan en el siguiente poll y el fallo queda visible en `/rules/log` (nueva columna "Estado", campo `processed_incidents.failure_reason`).
- Los tonos subidos desde `/settings` se perdían en cada rebuild/redeploy del contenedor por falta de volumen persistente — `docker-compose.yml` monta ahora `./audio:/app/static/audio/tones`.

### Cambiado
- Catálogo de tonos de preámbulo reducido a solo "Urgente" (Clásico/Suave/Selectiva no encajaban tras escucharlos); migración de retirada segura (deshabilita, no borra) para instalaciones ya desplegadas.
- Convención de volúmenes Docker simplificada a rutas de un solo nivel bajo `docker/`: `./data`, `./logs`, `./audio`, `./voices`.

## [1.3.0] - 2026-09-02

### Añadido
- Columna "Población" y buscador por texto libre en el histórico de alertas (`/rules/log`).

## [1.2.1] - 2026-09-01

### Añadido
- Guía detallada de diseño (botones, formularios, modales, accesibilidad) para el sistema de diseño del dashboard.

## [1.2.0] - 2026-08-31

### Añadido
- Ajustes de síntesis de voz (TTS) y preview de voces Piper en `/settings`.
- Soporte de subida de tonos en MP3, normalizados automáticamente a 16kHz mono WAV.
- Alta manual de municipios y seed de la Comarca de l'Horta (Nord + Sud) en `/rules`.
- Rediseño minimalista del panel SIRENA, con gestión de voces Piper desde `/settings`.
- Rediseño de la sección de reglas (lista condensada + modales) y de zonas (control de volumen, borrado de logs por altavoz, fix de fechas en histórico).
- Logo oficial SIRENA en login, favicon y barra lateral.

### Cambiado
- Modelo de voz de Piper horneado en la imagen Docker (con seed del volumen), eliminando la recarga por request; timing añadido al pipeline TTS.

## [1.1.0] - 2026-08-30

### Cambiado
- Piper aislado del exterior en `docker-compose` (solo accesible desde el dashboard vía loopback).

## [1.0.0] - 2026-08-29

### Añadido — Firmware (`esp32s3-firmware/ip-speaker/`)
- Hito 0: pinout real del hardware documentado a partir de la demo oficial de Waveshare.
- Hito 1: WiFi + servidor UDP + reproducción de PCM crudo audible.
- Hito 2: API HTTP de estado y control (`GET /status`, `POST /volume`).
- Hito 3: protocolo UDP con cabecera y tipos de mensaje (`START`/`AUDIO`/`END`/`PING`/`PONG`).
- Hito 4: integración de Opus (decodificación + PLC ante pérdida de paquetes).
- Hito 5: portal de configuración WiFi/IP en modo AP + persistencia en NVS.

### Añadido — Centro de mando (`docker/dashboard/`)
- Hito 7: primera versión del centro de mando Docker — gestión de altavoces/zonas, envío manual de mensajes y alertas automáticas sobre el feed 112CV.
- Rebrand a SIRENA, MAC real por altavoz, altavoces deshabilitables.
- Efecto de LEDs tipo Alexa en el anillo WS2812 al reproducir audio.
- LED azul de estado, ajustes de retención/sondeo, auditoría e histórico por altavoz.
- Preview de audio en envío manual y gestión de tonos por regla.
- Tono "Selectiva" (señal de protección civil).
- Script `update.sh` para despliegue en VPS con healthcheck y rollback.
- Re-escaneo del feed 112CV y multiselect con búsqueda.

### Corregido
- `last_message_at` de `/status` refleja el instante real del mensaje, no el del poll.
- Reproductor de preview de tonos y regeneración del tono "Selectiva".
- Error interno al eliminar una regla ya usada en alguna alerta.
- Resurrección de tonos borrados por el usuario tras reiniciar el contenedor.
- Taxonomía 112CV vacía, ding en envío manual, historial largo, UI de zonas/altavoces.
