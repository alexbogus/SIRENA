"""Wrapper HTTP mínimo sobre piper-tts: POST /synthesize {"text": ...} -> WAV.
Más simple que adoptar el protocolo Wyoming para un único cliente interno (el
dashboard).

A diferencia de una versión anterior de este fichero (que invocaba el
binario `piper` por subprocess en cada request, recargando el modelo ONNX
desde disco cada vez), este servidor usa la API Python de piper-tts
(`PiperVoice`) y mantiene los modelos cargados en memoria -- uno por "voice"
solicitada, cacheados en `_voices` -- reutilizando la sesión de onnxruntime
entre requests. La carga de modelo es el coste dominante de latencia por
request (más aún en CPUs sin AVX/AVX2), así que pagarla una sola vez al
arrancar el proceso en vez de en cada síntesis es la optimización de mayor
impacto.

Además de "text", /synthesize acepta los mismos parámetros opcionales de
síntesis que la versión anterior (si no vienen informados, se usa el default
del propio modelo): "voice" (nombre de fichero bajo VOICES_DIR, para elegir
entre los modelos instalados), "speaker" (id de locutor para modelos
multi-speaker como es_ES-sharvard-medium), y "length_scale" / "noise_scale" /
"noise_w" / "sentence_silence"."""
import io
import logging
import os
import time
import wave
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from piper import PiperVoice, SynthesisConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("piper-server")

app = Flask(__name__)

VOICES_DIR = Path(os.environ.get("PIPER_VOICES_DIR", "/voices"))
VOICE_MODEL = os.environ.get("PIPER_VOICE_MODEL", "/voices/es_ES-davefx-medium.onnx")

# Modelos ya cargados en memoria, indexados por ruta absoluta. Se rellena de
# forma perezosa (primera vez que se pide cada "voice"), salvo el modelo por
# defecto que se precarga al importar este módulo (ver más abajo).
_voices: dict[str, PiperVoice] = {}


def _load_voice(model_path: Path) -> PiperVoice:
    key = str(model_path)
    voice = _voices.get(key)
    if voice is None:
        logger.info(f"Cargando modelo Piper en memoria: {model_path}")
        t0 = time.monotonic()
        voice = PiperVoice.load(model_path)
        _voices[key] = voice
        logger.info(f"Modelo cargado en {time.monotonic() - t0:.2f}s: {model_path}")
    return voice


def _resolve_voice_model(voice: str | None) -> Path:
    """Resuelve "voice" (nombre de fichero) a una ruta dentro de VOICES_DIR.
    Se restringe explícitamente a VOICES_DIR (Path.name descarta cualquier
    componente de directorio) para que el body del POST no pueda apuntar a
    un fichero arbitrario del contenedor."""
    if not voice:
        return Path(VOICE_MODEL)
    candidate = VOICES_DIR / Path(voice).name
    return candidate if candidate.is_file() else Path(VOICE_MODEL)


def _float_or_none(value) -> float | None:
    return float(value) if value is not None else None


def _synthesize_wav_bytes(
    voice: PiperVoice, text: str, syn_config: SynthesisConfig, sentence_silence: float
) -> bytes:
    """Sintetiza `text` frase a frase (PiperVoice.synthesize produce un
    AudioChunk por frase) insertando `sentence_silence` segundos de silencio
    entre frases -- replica el comportamiento de `piper --sentence-silence`
    de la CLI anterior, que la API de más alto nivel `synthesize_wav` no
    soporta directamente."""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            params_set = False
            for i, chunk in enumerate(voice.synthesize(text, syn_config)):
                if not params_set:
                    wav_file.setframerate(chunk.sample_rate)
                    wav_file.setsampwidth(chunk.sample_width)
                    wav_file.setnchannels(chunk.sample_channels)
                    params_set = True
                if i > 0 and sentence_silence > 0:
                    n_bytes = int(chunk.sample_rate * sentence_silence) * chunk.sample_width
                    wav_file.writeframes(b"\x00" * n_bytes)
                wav_file.writeframes(chunk.audio_int16_bytes)
        return wav_io.getvalue()


@app.route("/synthesize", methods=["POST"])
def synthesize():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "falta 'text'"}), 400

    voice_model = _resolve_voice_model(data.get("voice"))

    try:
        speaker = data.get("speaker")
        syn_config = SynthesisConfig(
            speaker_id=int(speaker) if speaker is not None else None,
            length_scale=_float_or_none(data.get("length_scale")),
            noise_scale=_float_or_none(data.get("noise_scale")),
            noise_w_scale=_float_or_none(data.get("noise_w")),
        )
        sentence_silence = float(data.get("sentence_silence") or 0.0)
    except (TypeError, ValueError):
        return jsonify({"error": "parámetro de síntesis inválido"}), 400

    try:
        voice = _load_voice(voice_model)
        t0 = time.monotonic()
        wav_bytes = _synthesize_wav_bytes(voice, text, syn_config, sentence_silence)
        logger.info(f"Síntesis Piper: {time.monotonic() - t0:.2f}s (texto {len(text)} chars)")
    except Exception:
        logger.exception("Fallo de síntesis Piper")
        return jsonify({"error": "fallo de síntesis"}), 500

    return send_file(io.BytesIO(wav_bytes), mimetype="audio/wav")


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "voice_model": VOICE_MODEL,
        "voice_model_exists": os.path.exists(VOICE_MODEL),
        "loaded_voices": list(_voices.keys()),
    })


# Precarga el modelo por defecto al importar el módulo, para que el coste de
# carga se pague una sola vez al arrancar el contenedor (con gunicorn
# --preload, en el proceso master antes del fork de los workers) y no en el
# primer envío de un usuario.
_load_voice(Path(VOICE_MODEL))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100)
