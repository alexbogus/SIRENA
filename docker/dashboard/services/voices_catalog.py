"""Catálogo de voces Piper en español descargables desde /settings.

Se lee de una copia vendorizada (data_static/piper_voices_es.json) del
voices.json oficial de rhasspy/piper-voices, filtrada a idiomas es_* y
regenerada a mano de vez en cuando con scripts/update_voices_catalog.py --
el dashboard nunca hace ese fetch en runtime, solo lee el fichero local, así
que /settings no depende de que HuggingFace esté disponible para mostrarse."""
import json

import config
import models.voices as voices_model

_CATALOG_PATH = config.BASE_DIR / "data_static" / "piper_voices_es.json"
_HF_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

_catalog: list[dict] | None = None


def load_catalog() -> list[dict]:
    """Catálogo normalizado, cacheado en memoria tras la primera lectura
    (el fichero es estático dentro de la imagen, no cambia en runtime)."""
    global _catalog
    if _catalog is None:
        raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        _catalog = [_normalize(v) for v in raw.values()]
        _catalog.sort(key=lambda v: (v["language_code"], v["key"]))
    return _catalog


def _normalize(voice: dict) -> dict:
    onnx, onnx_json = voice["onnx"], voice["onnx_json"]
    return {
        "key": voice["key"],
        "filename": f"{voice['key']}.onnx",
        "json_filename": f"{voice['key']}.onnx.json",
        "language_code": voice["language_code"],
        "language_name": voice["language_name"],
        "quality": voice["quality"],
        "num_speakers": voice["num_speakers"],
        "speaker_id_map": voice["speaker_id_map"],
        "size_bytes": onnx["size_bytes"] + onnx_json["size_bytes"],
        "url_onnx": f"{_HF_BASE_URL}/{onnx['path']}",
        "md5_onnx": onnx["md5_digest"],
        "size_bytes_onnx": onnx["size_bytes"],
        "url_onnx_json": f"{_HF_BASE_URL}/{onnx_json['path']}",
        "md5_onnx_json": onnx_json["md5_digest"],
        "size_bytes_onnx_json": onnx_json["size_bytes"],
    }


def get(voice_key: str) -> dict | None:
    return next((v for v in load_catalog() if v["key"] == voice_key), None)


def installed_keys() -> set[str]:
    return {v["filename"].removesuffix(".onnx") for v in voices_model.list_installed()}
