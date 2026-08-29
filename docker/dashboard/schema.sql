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
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS speaker_status (
    speaker_id          INTEGER PRIMARY KEY REFERENCES speakers(id) ON DELETE CASCADE,
    firmware_version     TEXT,
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
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,    -- 'manual' | 'auto_112cv'
    text          TEXT NOT NULL,
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
