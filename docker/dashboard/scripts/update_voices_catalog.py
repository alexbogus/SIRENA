#!/usr/bin/env python3
"""Regenera data_static/piper_voices_es.json a partir del catálogo oficial
de Piper (rhasspy/piper-voices en HuggingFace, tag v1.0.0).

Ejecución manual únicamente, de vez en cuando -- el dashboard nunca hace
esta descarga en runtime, solo lee el fichero ya vendorizado. Requiere
`requests` (ya está en requirements.txt).

Uso: python3 scripts/update_voices_catalog.py
"""
import json
from pathlib import Path

import requests

VOICES_JSON_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/voices.json"
OUT_PATH = Path(__file__).resolve().parent.parent / "data_static" / "piper_voices_es.json"


def main() -> None:
    resp = requests.get(VOICES_JSON_URL, timeout=30)
    resp.raise_for_status()
    catalog = resp.json()

    es_voices = {}
    for key, voice in catalog.items():
        if not voice.get("language", {}).get("code", "").startswith("es_"):
            continue
        onnx_path = next(p for p in voice["files"] if p.endswith(".onnx"))
        json_path = f"{onnx_path}.json"
        es_voices[key] = {
            "key": key,
            "language_code": voice["language"]["code"],
            "language_name": voice["language"]["name_native"],
            "quality": voice["quality"],
            "num_speakers": voice["num_speakers"],
            "speaker_id_map": voice.get("speaker_id_map") or {},
            "onnx": {
                "path": onnx_path,
                "size_bytes": voice["files"][onnx_path]["size_bytes"],
                "md5_digest": voice["files"][onnx_path]["md5_digest"],
            },
            "onnx_json": {
                "path": json_path,
                "size_bytes": voice["files"][json_path]["size_bytes"],
                "md5_digest": voice["files"][json_path]["md5_digest"],
            },
        }

    OUT_PATH.write_text(
        json.dumps(es_voices, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{len(es_voices)} voces es_* escritas en {OUT_PATH}")


if __name__ == "__main__":
    main()
