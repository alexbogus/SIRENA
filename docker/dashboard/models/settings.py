import bcrypt

import config
import models.voices as voices_model
from db import db_cursor

_DEFAULTS = {
    "dashboard_password_hash": "",
    "auto_alerts_enabled": "1",
    "cv112_poll_interval_s": str(config.DEFAULT_CV112_POLL_INTERVAL_S),
    "status_poll_interval_s": str(config.DEFAULT_STATUS_POLL_INTERVAL_S),
    # Retención en BD de mensajes/errores de altavoz/auditoría (Fase 9c).
    "db_log_retention_days": "90",
    # Retención del estado de dedupe del 112CV (processed_incidents). Se
    # gestiona por separado del retention de logs porque cumple una función
    # distinta (evitar reenvíos), no es un log de auditoría.
    "dedupe_retention_days": "90",
    # Parámetros de síntesis de voz (Piper), ver services/tts.py. Los
    # defaults de noise_scale/noise_w son ligeramente más altos que los de
    # Piper (0.667/0.8) para que la prosodia suene menos plana/robótica.
    # sharvard-medium es multi-speaker (0=masculina, 1=femenina), mismo
    # acento de España que davefx -- permite elegir género sin cambiar de
    # acento.
    "tts_voice": "es_ES-sharvard-medium.onnx",
    "tts_speaker_id": "1",
    "tts_length_scale": "1.0",
    "tts_noise_scale": "0.75",
    "tts_noise_w": "0.85",
    "tts_sentence_silence": "0.3",
}

# Límites razonables para los campos numéricos editables desde /settings.
MIN_POLL_INTERVAL_S = 10
MAX_POLL_INTERVAL_S = 3600
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
MIN_TTS_LENGTH_SCALE = 0.5
MAX_TTS_LENGTH_SCALE = 2.0
MIN_TTS_NOISE = 0.0
MAX_TTS_NOISE = 1.0
MIN_TTS_SENTENCE_SILENCE = 0.0
MAX_TTS_SENTENCE_SILENCE = 2.0

def tts_voices_choices() -> list[dict]:
    """Voces instaladas en VOICES_DIR (autodescubiertas, ver models/voices.py),
    con la misma forma {filename, speaker_id, label} que antes exponía el
    catálogo hardcodeado TTS_VOICES -- gestionables ahora desde /settings
    (descarga/eliminación) en vez de vía download_voice.sh a mano."""
    return voices_model.list_installed()


def get(key: str) -> str | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is not None:
        return row["value"]
    return _DEFAULTS.get(key)


def set(key: str, value: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def is_password_set() -> bool:
    return bool(get("dashboard_password_hash"))


def set_password(plain_password: str) -> None:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    set("dashboard_password_hash", hashed.decode("utf-8"))


def check_password(plain_password: str) -> bool:
    hashed = get("dashboard_password_hash")
    if not hashed:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed.encode("utf-8"))


def auto_alerts_enabled() -> bool:
    return get("auto_alerts_enabled") == "1"


def set_auto_alerts_enabled(enabled: bool) -> None:
    set("auto_alerts_enabled", "1" if enabled else "0")


def cv112_poll_interval_s() -> int:
    return int(get("cv112_poll_interval_s"))


def status_poll_interval_s() -> int:
    return int(get("status_poll_interval_s"))


def db_log_retention_days() -> int:
    return int(get("db_log_retention_days"))


def dedupe_retention_days() -> int:
    return int(get("dedupe_retention_days"))


def tts_voice() -> str:
    return get("tts_voice")


def tts_speaker_id() -> int | None:
    value = get("tts_speaker_id")
    return int(value) if value not in (None, "") else None


def tts_length_scale() -> float:
    return float(get("tts_length_scale"))


def tts_noise_scale() -> float:
    return float(get("tts_noise_scale"))


def tts_noise_w() -> float:
    return float(get("tts_noise_w"))


def tts_sentence_silence() -> float:
    return float(get("tts_sentence_silence"))
