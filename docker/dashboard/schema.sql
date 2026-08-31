-- Esquema del centro de mando. Idempotente (CREATE TABLE IF NOT EXISTS) para
-- poder aplicarse en cada arranque del contenedor sin migraciones formales.

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS speakers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    ip         TEXT NOT NULL UNIQUE,
    port       INTEGER NOT NULL DEFAULT 5005,
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS speaker_status (
    speaker_id          INTEGER PRIMARY KEY REFERENCES speakers(id) ON DELETE CASCADE,
    firmware_version     TEXT,
    mac                    TEXT,
    rssi_dbm              INTEGER,
    state                  TEXT,
    volume_percent        INTEGER,
    last_message_at       TEXT,
    last_healthcheck_at   TEXT,
    uptime_seconds         INTEGER,
    last_poll_ok           INTEGER NOT NULL DEFAULT 0,
    last_poll_at           TEXT
);

CREATE TABLE IF NOT EXISTS zones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS speaker_zones (
    speaker_id INTEGER NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
    zone_id    INTEGER NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    PRIMARY KEY (speaker_id, zone_id)
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    municipios      TEXT,   -- JSON array de strings, NULL/[] = todos
    categorias      TEXT,   -- JSON array de rutas de taxonomia (["Incendio"], ["Incendio","Vegetación"]...), NULL/[] = todas
    target_zone_id  INTEGER REFERENCES zones(id),  -- NULL = target especial "todos"
    tone_id         INTEGER REFERENCES tones(id),  -- NULL = usa el tono por defecto global
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Catálogo de tonos de preámbulo disponibles para los avisos (manuales y
-- automáticos). Solo una fila puede tener is_default = 1 a la vez (se
-- garantiza en models/tones.py, no con una constraint SQL). Sembrado por
-- primera vez en db.py::init_db() con los WAV generados por
-- scripts/generate_tones.py.
CREATE TABLE IF NOT EXISTS tones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    filename   TEXT NOT NULL UNIQUE,   -- relativo a static/audio/tones/
    enabled    INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,    -- 'manual' | 'auto_112cv'
    text          TEXT NOT NULL,
    target_label  TEXT,             -- foto fija del destino en el momento del envío ("Todos", "Cocina, CECOM"...) -- no depende de que la zona siga existiendo
    rule_id       INTEGER REFERENCES alert_rules(id),
    incident_id   INTEGER,
    sent_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS message_targets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    speaker_id      INTEGER NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
    send_ok         INTEGER NOT NULL DEFAULT 0,
    delivery_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'confirmed' | 'unconfirmed'
    checked_at      TEXT
);

-- Plantillas de texto rápidas para el envío manual (/send). Gestionadas
-- desde Configuración, igual que los tonos, pero sin default/enabled: solo
-- alta y borrado.
CREATE TABLE IF NOT EXISTS message_templates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS processed_incidents (
    incident_id         INTEGER PRIMARY KEY,   -- properties.id del geojson
    first_seen_at        TEXT NOT NULL DEFAULT (datetime('now')),
    last_checked_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_raw_description  TEXT,                 -- properties.description.es tal cual, para detectar cambios
    last_municipio         TEXT,                 -- properties.municipio, para poblar el desplegable de reglas
    matched_rule_id       INTEGER REFERENCES alert_rules(id),
    message_id            INTEGER REFERENCES messages(id)  -- NOT NULL = estado terminal, ya anunciado
);

CREATE TABLE IF NOT EXISTS geocode_cache (
    lat_lon_key TEXT PRIMARY KEY,   -- lat,lon redondeados a 5 decimales
    result_text TEXT,               -- NULL si Nominatim no devolvió nada util
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_health (
    component            TEXT PRIMARY KEY,   -- 'cv112_feed' | 'piper'
    last_ok_at             TEXT,
    last_error_at           TEXT,
    last_error_message      TEXT,
    consecutive_failures    INTEGER NOT NULL DEFAULT 0
);

-- Catálogo de municipios y rutas de taxonomía vistos alguna vez en el feed
-- del 112CV. A diferencia de processed_incidents (que se purga), estas dos
-- tablas NUNCA se purgan: son el catálogo que puebla los desplegables de
-- /rules y lo que permite detectar "categoría nueva" en cada poll sin
-- depender de cuánto dedupe histórico sigue vivo. Crecimiento acotado (el
-- número de municipios/categorías reales es pequeño y estable).
CREATE TABLE IF NOT EXISTS known_municipios (
    municipio     TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS known_taxonomy_paths (
    raw_description TEXT PRIMARY KEY,  -- properties.description.es tal cual ("Incendio > Vegetación > Forestal")
    first_seen_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Logs retenidos en BD (retención configurable, ver settings
-- 'log_retention_days'). Deliberadamente NO incluye eventos crudos del
-- feed 112CV -- eso vive solo en processed_incidents (dedupe, retención
-- propia 'dedupe_retention_days') y en los logs de fichero.
CREATE TABLE IF NOT EXISTS speaker_error_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker_id  INTEGER REFERENCES speakers(id) ON DELETE CASCADE,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now')),
    message     TEXT NOT NULL
);

-- Estado de descargas de modelos de voz Piper lanzadas desde /settings
-- (services/voice_downloader.py). voice_key es la clave del catálogo
-- vendorizado (data_static/piper_voices_es.json), no el nombre de fichero.
CREATE TABLE IF NOT EXISTS voice_downloads (
    voice_key    TEXT PRIMARY KEY,
    status       TEXT NOT NULL,      -- 'running' | 'done' | 'error'
    error        TEXT,
    started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at  TEXT
);

-- Etiquetas legibles curadas por el usuario para voces instaladas
-- (filename + speaker_id, ver models/voices.py). Si no hay fila aquí se
-- genera una etiqueta por defecto a partir de los metadatos del .onnx.json.
-- speaker_id usa el sentinel -1 para "sin locutor" (modelo mono-speaker) en
-- vez de NULL: SQLite trata cada NULL como distinto en una PRIMARY KEY
-- compuesta, así que dos filas con speaker_id NULL no chocarían entre sí y
-- el upsert de set_label() insertaría duplicados en vez de actualizar.
CREATE TABLE IF NOT EXISTS voice_labels (
    filename   TEXT NOT NULL,
    speaker_id INTEGER NOT NULL DEFAULT -1,
    label      TEXT NOT NULL,
    PRIMARY KEY (filename, speaker_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now')),
    entity_type TEXT NOT NULL,   -- 'speaker' | 'zone'
    action      TEXT NOT NULL,   -- 'created' | 'updated' | 'deleted'
    entity_name TEXT NOT NULL,
    details     TEXT             -- texto libre, ej. "ip 10.0.1.56 -> 10.0.1.57"
);
