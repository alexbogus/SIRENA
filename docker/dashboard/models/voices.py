"""Autodescubrimiento y gestión de los modelos de voz Piper instalados en
VOICES_DIR (volumen compartido con el sidecar piper), más el estado de
descargas en curso. Sustituye al catálogo hardcodeado que existía antes en
models/settings.py: cualquier par .onnx/.onnx.json presente en el
filesystem aparece automáticamente en /settings."""
import json

import config
from db import db_cursor

VOICES_DIR = config.PIPER_VOICES_DIR


def _read_sidecar(onnx_path) -> dict | None:
    json_path = onnx_path.with_suffix(onnx_path.suffix + ".json")
    if not json_path.is_file():
        config.get_logger("voices").warning(
            f"Modelo sin sidecar .onnx.json, se omite: {onnx_path.name}"
        )
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config.get_logger("voices").warning(
            f"Sidecar .onnx.json ilegible, se omite: {json_path.name}"
        )
        return None


def _default_label(filename: str, speaker_id: int | None, speaker_id_map: dict) -> str:
    stem = filename.removesuffix(".onnx")
    if speaker_id is None:
        return stem
    name = next((k for k, v in speaker_id_map.items() if v == speaker_id), None)
    return f"{stem} ({name})" if name else f"{stem} (locutor {speaker_id})"


def list_installed() -> list[dict]:
    """Una fila por locutor: modelos multi-speaker producen varias filas
    con el mismo filename y distinto speaker_id (igual que el antiguo
    catálogo hardcodeado TTS_VOICES)."""
    if not VOICES_DIR.is_dir():
        return []

    labels = _labels_by_key()
    rows = []
    for onnx_path in sorted(VOICES_DIR.glob("*.onnx")):
        meta = _read_sidecar(onnx_path)
        if meta is None:
            continue
        filename = onnx_path.name
        num_speakers = meta.get("num_speakers", 1)
        speaker_id_map = meta.get("speaker_id_map") or {}
        language_code = (meta.get("language") or {}).get("code", "")
        size_bytes = onnx_path.stat().st_size
        speaker_ids = list(range(num_speakers)) if num_speakers > 1 else [None]
        for speaker_id in speaker_ids:
            label = labels.get((filename, speaker_id)) or _default_label(
                filename, speaker_id, speaker_id_map
            )
            rows.append({
                "filename": filename,
                "speaker_id": speaker_id,
                "language_code": language_code,
                "num_speakers": num_speakers,
                "size_bytes": size_bytes,
                "label": label,
            })
    return rows


def get_installed(filename: str, speaker_id: int | None) -> dict | None:
    return next(
        (v for v in list_installed() if v["filename"] == filename and v["speaker_id"] == speaker_id),
        None,
    )


_NO_SPEAKER = -1  # sentinel para speaker_id en voice_labels, ver schema.sql


def _labels_by_key() -> dict[tuple[str, int | None], str]:
    with db_cursor() as cur:
        rows = cur.execute("SELECT filename, speaker_id, label FROM voice_labels").fetchall()
    return {
        (r["filename"], None if r["speaker_id"] == _NO_SPEAKER else r["speaker_id"]): r["label"]
        for r in rows
    }


def set_label(filename: str, speaker_id: int | None, label: str) -> None:
    db_speaker_id = _NO_SPEAKER if speaker_id is None else speaker_id
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO voice_labels(filename, speaker_id, label) VALUES (?, ?, ?) "
            "ON CONFLICT(filename, speaker_id) DO UPDATE SET label = excluded.label",
            (filename, db_speaker_id, label),
        )


def delete_installed(filename: str) -> None:
    (VOICES_DIR / filename).unlink(missing_ok=True)
    json_name = filename + ".json"
    (VOICES_DIR / json_name).unlink(missing_ok=True)
    with db_cursor() as cur:
        cur.execute("DELETE FROM voice_labels WHERE filename = ?", (filename,))


def get_download(voice_key: str) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT * FROM voice_downloads WHERE voice_key = ?", (voice_key,)
        ).fetchone()
    return dict(row) if row else None


def list_running_downloads() -> list[str]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT voice_key FROM voice_downloads WHERE status = 'running'"
        ).fetchall()
    return [r["voice_key"] for r in rows]


def start_download_row(voice_key: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO voice_downloads(voice_key, status, error, finished_at) "
            "VALUES (?, 'running', NULL, NULL) "
            "ON CONFLICT(voice_key) DO UPDATE SET "
            "status = 'running', error = NULL, started_at = datetime('now'), finished_at = NULL",
            (voice_key,),
        )


def set_download_status(voice_key: str, status: str, error: str | None = None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE voice_downloads SET status = ?, error = ?, finished_at = datetime('now') "
            "WHERE voice_key = ?",
            (status, error, voice_key),
        )


def mark_interrupted_downloads() -> None:
    """Se llama al arrancar el dashboard: cualquier descarga que quedó
    'running' es de un proceso anterior que ya no existe (el scheduler es
    en memoria, no sobrevive a un reinicio del contenedor)."""
    with db_cursor() as cur:
        cur.execute(
            "UPDATE voice_downloads SET status = 'error', "
            "error = 'Interrumpida por reinicio del dashboard', finished_at = datetime('now') "
            "WHERE status = 'running'"
        )
