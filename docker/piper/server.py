"""Wrapper HTTP mínimo sobre el binario piper: POST /synthesize {"text": ...}
-> WAV. Más simple que adoptar el protocolo Wyoming para un único cliente
interno (el dashboard).

Además de "text", /synthesize acepta parámetros opcionales de síntesis que
se pasan tal cual como flags de la CLI de piper si vienen informados (si no,
se omite el flag y manda el default de Piper): "voice" (nombre de fichero
bajo VOICES_DIR, para elegir entre los modelos instalados), "speaker" (id de
locutor para modelos multi-speaker como es_ES-sharvard-medium), y
"length_scale" / "noise_scale" / "noise_w" / "sentence_silence"."""
import os
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

VOICES_DIR = Path(os.environ.get("PIPER_VOICES_DIR", "/voices"))
VOICE_MODEL = os.environ.get("PIPER_VOICE_MODEL", "/voices/es_ES-davefx-medium.onnx")

_FLOAT_PARAMS = {
    "length_scale": "--length-scale",
    "noise_scale": "--noise-scale",
    "noise_w": "--noise-w",
    "sentence_silence": "--sentence-silence",
}


def _resolve_voice_model(voice: str | None) -> str | Path:
    """Resuelve "voice" (nombre de fichero) a una ruta dentro de VOICES_DIR.
    Se restringe explícitamente a VOICES_DIR (Path.name descarta cualquier
    componente de directorio) para que el body del POST no pueda apuntar a
    un fichero arbitrario del contenedor."""
    if not voice:
        return VOICE_MODEL
    candidate = VOICES_DIR / Path(voice).name
    return candidate if candidate.is_file() else VOICE_MODEL


@app.route("/synthesize", methods=["POST"])
def synthesize():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "falta 'text'"}), 400

    voice_model = _resolve_voice_model(data.get("voice"))

    args = ["piper", "--model", str(voice_model)]

    try:
        speaker = data.get("speaker")
        if speaker is not None:
            args += ["--speaker", str(int(speaker))]

        for key, flag in _FLOAT_PARAMS.items():
            value = data.get(key)
            if value is not None:
                args += [flag, str(float(value))]
    except (TypeError, ValueError):
        return jsonify({"error": "parámetro de síntesis inválido"}), 400

    out_fd = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out_fd.close()
    args += ["--output_file", out_fd.name]
    try:
        result = subprocess.run(
            args,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return jsonify({"error": result.stderr.decode("utf-8", errors="replace")}), 500
        return send_file(out_fd.name, mimetype="audio/wav")
    except subprocess.TimeoutExpired:
        return jsonify({"error": "timeout de síntesis"}), 504
    finally:
        # send_file ya envió el contenido; lo borramos después de responder
        # no es trivial con Flask sync -- se limpia en el siguiente ciclo del
        # SO via /tmp, volumen efímero del contenedor.
        pass


@app.route("/health")
def health():
    return jsonify({"ok": True, "voice_model": VOICE_MODEL, "voice_model_exists": os.path.exists(VOICE_MODEL)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100)
