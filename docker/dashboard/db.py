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
    ("known_municipios", "source", "TEXT NOT NULL DEFAULT 'feed'"),
]

# Municipios de la Comarca de l'Horta (Nord + Sud) sembrados en el arranque
# para que estén disponibles en /rules aunque el feed 112CV no haya reportado
# todavía ningún incidente ahí -- ver models/taxonomy.py para el porqué
# (known_municipios solo se rellena hoy con municipios que ya han tenido un
# incidente real). Grafía: la verificada contra el feed real donde fue
# posible (Paterna, Moncada, Puçol, Puig, Quart de Poblet, Xirivella,
# Alcàsser, Alaquàs); el resto es la grafía oficial (Viquipèdia) a falta de
# verificación empírica -- si el feed usa otra grafía para alguno, aparecerá
# como fila nueva con source='feed' y habrá que fusionarlas a mano.
_HORTA_MUNICIPIOS = [
    # L'Horta Nord
    "Paterna", "Burjassot", "Alboraia", "Moncada", "Puçol", "Massamagrell",
    "Godella", "Meliana", "Rafelbunyol", "Tavernes Blanques", "Puig",
    "la Pobla de Farnals", "Foios", "Rocafort", "Almàssera", "Museros",
    "Albuixec", "Albalat dels Sorells", "Bonrepòs i Mirambell", "Vinalesa",
    "Alfara del Patriarca", "Massalfassar", "Emperador",
    # L'Horta Sud
    "Alaquàs", "Albal", "Alcàsser", "Aldaia", "Alfafar", "Benetússer",
    "Beniparrell", "Catarroja", "Llocnou de la Corona", "Manises",
    "Massanassa", "Mislata", "Paiporta", "Picanya", "Picassent",
    "Quart de Poblet", "Sedaví", "Silla", "Torrent", "Xirivella",
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
        _seed_known_municipios(conn)
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


def _seed_known_municipios(conn: sqlite3.Connection) -> None:
    from models.taxonomy import normalized_forms  # import tardío: evita ciclo db <-> models.taxonomy

    existing = [row["municipio"] for row in conn.execute("SELECT municipio FROM known_municipios")]
    existing_forms = {f for m in existing for f in normalized_forms(m)}
    for municipio in _HORTA_MUNICIPIOS:
        if normalized_forms(municipio) & existing_forms:
            continue  # ya está (por el seed de una ejecución previa, o porque el feed ya lo reportó)
        conn.execute(
            "INSERT INTO known_municipios(municipio, source) VALUES (?, 'manual') "
            "ON CONFLICT(municipio) DO NOTHING",
            (municipio,),
        )
        existing_forms |= normalized_forms(municipio)


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
