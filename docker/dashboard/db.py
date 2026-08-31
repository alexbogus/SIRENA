import sqlite3
from contextlib import contextmanager

import config


# Columnas añadidas a tablas ya existentes en despliegues previos.
# CREATE TABLE IF NOT EXISTS no altera tablas que ya existen, así que estas
# ALTER TABLE cubren la migración de instalaciones anteriores a esta
# columna (no hay sistema de migraciones formal en este proyecto).
_COLUMN_MIGRATIONS = [
    ("messages", "target_label", "TEXT"),
    ("zones", "enabled", "INTEGER NOT NULL DEFAULT 1"),
    ("alert_rules", "tone_id", "INTEGER REFERENCES tones(id)"),
    ("speakers", "enabled", "INTEGER NOT NULL DEFAULT 1"),
    ("speakers", "description", "TEXT"),
    ("speaker_status", "mac", "TEXT"),
]

# Tonos sembrados la primera vez que arranca el contenedor (tabla `tones`
# vacía). Los WAV correspondientes los genera scripts/generate_tones.py y se
# versionan en static/audio/tones/ -- este seed solo crea las filas de BD.
_DEFAULT_TONES = [
    ("Clásico", "clasico.wav"),
    ("Urgente", "urgente.wav"),
    ("Suave", "suave.wav"),
    ("Selectiva", "selectiva.wav"),
]

# Tonos añadidos después del primer arranque de instalaciones ya existentes
# (donde _seed_default_tones ya no actúa porque la tabla no está vacía). Cada
# uno se inserta como mucho una vez: se marca en `settings` con la key de
# abajo para no resucitarlo si el usuario lo borra luego desde /settings
# (comprobar solo "¿existe ya en `tones`?" resucitaba el tono -- sin su WAV,
# porque el borrado real si se lo había cargado -- en cada reinicio).
_ADDITIONAL_TONES = [
    ("tones_seeded_selectiva", "Selectiva", "selectiva.wav"),
]


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = (config.BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema_sql)
        _apply_column_migrations(conn)
        _seed_default_tones(conn)
        _seed_additional_tones(conn)
        conn.commit()


def _apply_column_migrations(conn: sqlite3.Connection) -> None:
    for table, column, col_type in _COLUMN_MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _seed_default_tones(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) AS n FROM tones").fetchone()["n"]
    if count > 0:
        return
    for i, (name, filename) in enumerate(_DEFAULT_TONES):
        conn.execute(
            "INSERT INTO tones(name, filename, enabled, is_default) VALUES (?, ?, 1, ?)",
            (name, filename, 1 if i == 0 else 0),
        )


def _seed_additional_tones(conn: sqlite3.Connection) -> None:
    seeded = {
        row["key"]
        for row in conn.execute("SELECT key FROM settings WHERE key LIKE 'tones_seeded_%'")
    }
    existing_filenames = {row["filename"] for row in conn.execute("SELECT filename FROM tones")}
    for marker_key, name, filename in _ADDITIONAL_TONES:
        if marker_key in seeded:
            continue
        # Backfill: si la fila ya existe (instalaciones que arrancaron con
        # esta versión antes de que existiera el marcador), no duplicar --
        # solo marcar como sembrado.
        if filename not in existing_filenames:
            conn.execute(
                "INSERT INTO tones(name, filename, enabled, is_default) VALUES (?, ?, 1, 0)",
                (name, filename),
            )
        conn.execute("INSERT INTO settings(key, value) VALUES (?, '1')", (marker_key,))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor():
    """Contexto que abre conexión, hace commit/rollback y cierra siempre."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
