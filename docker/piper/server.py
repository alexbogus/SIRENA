"""Wrapper HTTP mínimo sobre el binario piper: POST /synthesize {"text": ...}
-> WAV. Más simple que adoptar el protocolo Wyoming para un único cliente
interno (el dashboard)."""
import os
import subprocess
import tempfile

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

VOICE_MODEL = os.environ.get("PIPER_VOICE_MODEL", "/voices/es_ES-davefx-medium.onnx")


@app.route("/synthesize", methods=["POST"])
def synthesize():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "falta 'text'"}), 400

    out_fd = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out_fd.close()
    try:
        result = subprocess.run(
            ["piper", "--model", VOICE_MODEL, "--output_file", out_fd.name],
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
