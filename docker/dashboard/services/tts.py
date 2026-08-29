"""Cliente del sidecar Piper TTS + resampleo a 16kHz/mono/16-bit (formato
que exige _protocol_sender.load_pcm_chunks) + concatenación con el
preámbulo "ding-ding"."""
import subprocess
import tempfile
import wave
from pathlib import Path

import requests

import config

logger = config.get_logger("tts")

DING_PATH = config.BASE_DIR / "static" / "audio" / "ding.wav"
_SILENCE_MS = 200


def synthesize(text: str) -> str:
    """Sintetiza `text` con Piper y devuelve la ruta a un WAV temporal
    16kHz/mono/16-bit. Lanza excepción si Piper no responde -- quien llame
    decide cómo degradar (ver cv112_poller/manual_send)."""
    resp = requests.post(config.PIPER_URL, json={"text": text}, timeout=30)
    resp.raise_for_status()

    raw_fd = tempfile.NamedTemporaryFile(suffix="_piper_raw.wav", delete=False)
    raw_fd.write(resp.content)
    raw_fd.close()

    resampled_path = raw_fd.name.replace("_piper_raw.wav", "_piper_16k.wav")
    _resample_to_16k_mono(raw_fd.name, resampled_path)
    Path(raw_fd.name).unlink(missing_ok=True)
    return resampled_path


def _resample_to_16k_mono(src_path: str, dst_path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src_path,
         "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", dst_path],
        check=True,
    )


def build_alert_wav(text: str) -> str:
    """Sintetiza `text` y lo concatena con el ding + silencio de preámbulo.
    Devuelve la ruta a un WAV temporal 16kHz/mono/16-bit listo para
    services/sender.py."""
    speech_path = synthesize(text)
    out_fd = tempfile.NamedTemporaryFile(suffix="_alert.wav", delete=False)
    out_fd.close()
    _concat_wavs([str(DING_PATH), speech_path], out_fd.name, silence_ms=_SILENCE_MS)
    Path(speech_path).unlink(missing_ok=True)
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
