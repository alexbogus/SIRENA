"""Cliente del sidecar Piper TTS + resampleo a 16kHz/mono/16-bit (formato
que exige _protocol_sender.load_pcm_chunks) + concatenación con el
preámbulo "ding-ding"."""
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import requests

import config
import models.settings as settings_model
import models.tones as tones_model

logger = config.get_logger("tts")

_TONES_DIR = config.BASE_DIR / "static" / "audio" / "tones"
_SILENCE_MS = 200

# Abreviaturas/patrones frecuentes en el texto de envíos manuales y en las
# referencias de calle geocodificadas (Nominatim) que Piper/espeak-ng lee
# mal si se mandan tal cual. Lista basada en lo visto en uso real, no
# exhaustiva -- ampliar aquí según haga falta. El orden importa: los
# patrones con "\b" de vía deben ir antes que reglas más genéricas.
_TEXT_NORMALIZATIONS = [
    (re.compile(r"\bC/\s*", re.IGNORECASE), "calle "),
    (re.compile(r"\bAvda\.?\s*", re.IGNORECASE), "avenida "),
    (re.compile(r"\bAv\.\s*", re.IGNORECASE), "avenida "),
    (re.compile(r"\bCtra\.?\s*", re.IGNORECASE), "carretera "),
    (re.compile(r"\bPza\.?\s*", re.IGNORECASE), "plaza "),
    (re.compile(r"\bPl\.\s*", re.IGNORECASE), "plaza "),
    (re.compile(r"\bN-(\d+)\b", re.IGNORECASE), r"carretera nacional \1"),
    (re.compile(r"\bCV-(\d+)\b", re.IGNORECASE), r"C V \1"),
    (re.compile(r"\bkm\.?\s*(\d+)", re.IGNORECASE), r"kilómetro \1"),
    (re.compile(r"\b(\d{1,2}):(\d{2})\s*h?\b"), lambda m: f"{m.group(1)} {m.group(2)}"),
]


def _normalize_text(text: str) -> str:
    for pattern, replacement in _TEXT_NORMALIZATIONS:
        text = pattern.sub(replacement, text)
    return text


def synthesize(text: str, voice: str | None = None, speaker_id: int | None = None) -> str:
    """Sintetiza `text` con Piper y devuelve la ruta a un WAV temporal
    16kHz/mono/16-bit. Lanza excepción si Piper no responde -- quien llame
    decide cómo degradar (ver cv112_poller/manual_send).

    `voice`/`speaker_id` sobrescriben la voz por defecto de Configuración
    para esta llamada únicamente (usado por el preview de /send para probar
    otras voces sin tocar el ajuste global)."""
    payload = {
        "text": _normalize_text(text),
        "voice": voice or settings_model.tts_voice(),
        "length_scale": settings_model.tts_length_scale(),
        "noise_scale": settings_model.tts_noise_scale(),
        "noise_w": settings_model.tts_noise_w(),
        "sentence_silence": settings_model.tts_sentence_silence(),
    }
    speaker_id = speaker_id if speaker_id is not None else settings_model.tts_speaker_id()
    if speaker_id is not None:
        payload["speaker"] = speaker_id

    t0 = time.monotonic()
    resp = requests.post(config.PIPER_URL, json=payload, timeout=30)
    resp.raise_for_status()
    t_piper = time.monotonic() - t0
    logger.info(f"TTS síntesis Piper: {t_piper:.2f}s (texto {len(text)} chars)")

    raw_fd = tempfile.NamedTemporaryFile(suffix="_piper_raw.wav", delete=False)
    raw_fd.write(resp.content)
    raw_fd.close()

    resampled_path = raw_fd.name.replace("_piper_raw.wav", "_piper_16k.wav")
    t1 = time.monotonic()
    _resample_to_16k_mono(raw_fd.name, resampled_path)
    t_resample = time.monotonic() - t1
    logger.info(f"TTS resampleo ffmpeg: {t_resample:.2f}s")
    Path(raw_fd.name).unlink(missing_ok=True)
    return resampled_path


def _resample_to_16k_mono(src_path: str, dst_path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src_path,
         "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", dst_path],
        check=True,
    )


def build_alert_wav(
    text: str, tone_id: int | None = None, voice: str | None = None, speaker_id: int | None = None
) -> str:
    """Sintetiza `text` y lo concatena con el tono + silencio de preámbulo.
    `tone_id` selecciona un tono concreto (debe estar habilitado); si es
    None, o el tono indicado no está habilitado, se usa el tono marcado por
    defecto (models.tones). `voice`/`speaker_id` sobrescriben la voz por
    defecto para esta llamada (ver synthesize). Devuelve la ruta a un WAV
    temporal 16kHz/mono/16-bit listo para services/sender.py."""
    tone = tones_model.get(tone_id) if tone_id is not None else None
    if tone is None or not tone["enabled"]:
        tone = tones_model.get_default()
    tone_path = _TONES_DIR / tone["filename"]
    if not tone_path.exists():
        logger.warning(f"Tono {tone['name']!r} (id={tone['id']}) sin archivo en disco "
                        f"({tone_path}), usando tono por defecto")
        tone = tones_model.get_default()
        tone_path = _TONES_DIR / tone["filename"]

    t0 = time.monotonic()
    speech_path = synthesize(text, voice=voice, speaker_id=speaker_id)
    out_fd = tempfile.NamedTemporaryFile(suffix="_alert.wav", delete=False)
    out_fd.close()
    _concat_wavs([str(tone_path), speech_path], out_fd.name, silence_ms=_SILENCE_MS)
    Path(speech_path).unlink(missing_ok=True)
    logger.info(f"TTS build_alert_wav total: {time.monotonic() - t0:.2f}s")
    return out_fd.name


_MAX_PREVIEW_REPEATS = 5
_REPEAT_PAUSE_MS = 1000


def build_preview_wav(
    text: str,
    tone_id: int | None = None,
    voice: str | None = None,
    speaker_id: int | None = None,
    repeats: int = 1,
) -> str:
    """Como build_alert_wav, pero repite el resultado `repeats` veces (con
    una pausa entre medias) para pruebas de sonido/nivel desde /send. Solo
    se usa en el preview -- el envío real a los altavoces nunca repite."""
    repeats = max(1, min(_MAX_PREVIEW_REPEATS, repeats))
    alert_path = build_alert_wav(text, tone_id=tone_id, voice=voice, speaker_id=speaker_id)
    if repeats == 1:
        return alert_path

    out_fd = tempfile.NamedTemporaryFile(suffix="_alert_preview.wav", delete=False)
    out_fd.close()
    _concat_wavs([alert_path] * repeats, out_fd.name, silence_ms=_REPEAT_PAUSE_MS)
    Path(alert_path).unlink(missing_ok=True)
    return out_fd.name


def _concat_wavs(paths: list[str], out_path: str, silence_ms: int) -> None:
    with wave.open(out_path, "wb") as out:
        params_set = False
        for i, path in enumerate(paths):
            with wave.open(path, "rb") as w:
                if not params_set:
                    out.setnchannels(w.getnchannels())
                    out.setsampwidth(w.getsampwidth())
                    out.setframerate(w.getframerate())
                    params_set = True
                out.writeframes(w.readframes(w.getnframes()))
                if i < len(paths) - 1 and silence_ms > 0:
                    n_samples = int(w.getframerate() * silence_ms / 1000)
                    out.writeframes(b"\x00" * (n_samples * w.getsampwidth() * w.getnchannels()))
