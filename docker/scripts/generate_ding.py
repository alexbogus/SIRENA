#!/usr/bin/env python3
"""Genera el preámbulo sonoro "ding-ding" de las alertas automáticas: dos
tonos senoidales cortos con fade in/out, 16kHz/mono/16-bit (mismo formato
que exige _protocol_sender.load_pcm_chunks). Asset propio del proyecto, sin
copyright de terceros. Se ejecuta una vez en desarrollo, no en cada arranque
del contenedor -- el resultado se versiona en dashboard/static/audio/ding.wav.

Uso: python3 scripts/generate_ding.py
"""
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 16000
OUT_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "static" / "audio" / "ding.wav"

TONES = [(880, 0.15), (1046, 0.15)]  # (frecuencia Hz, duración s)
FADE_MS = 15
GAP_MS = 40


def _tone(freq: float, duration_s: float) -> list[int]:
    n = int(SAMPLE_RATE * duration_s)
    fade_samples = int(SAMPLE_RATE * FADE_MS / 1000)
    samples = []
    for i in range(n):
        amp = 12000
        if i < fade_samples:
            amp = amp * i / fade_samples
        elif i > n - fade_samples:
            amp = amp * (n - i) / fade_samples
        samples.append(int(amp * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)))
    return samples


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_samples: list[int] = []
    gap_samples = [0] * int(SAMPLE_RATE * GAP_MS / 1000)
    for i, (freq, dur) in enumerate(TONES):
        all_samples.extend(_tone(freq, dur))
        if i < len(TONES) - 1:
            all_samples.extend(gap_samples)

    with wave.open(str(OUT_PATH), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(struct.pack("<h", s) for s in all_samples))
    print(f"Generado {OUT_PATH} ({len(all_samples)/SAMPLE_RATE:.2f}s)")


if __name__ == "__main__":
    main()
