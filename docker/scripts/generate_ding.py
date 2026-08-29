#!/usr/bin/env python3
"""Genera el preámbulo sonoro de las alertas automáticas: 4 notas
(440/554/659/880Hz) con cadencia lenta de 2s entre el INICIO de cada una.
Cada nota suena a volumen pleno el primer segundo y luego empieza a
apagarse (fade), con la cola de ese fade solapándose con el arranque de la
siguiente nota (efecto campana, en vez de un corte seco cada 2s) -- 16kHz/
mono/16-bit, mismo formato que exige _protocol_sender.load_pcm_chunks.
Asset propio del proyecto, sin copyright de terceros. Se ejecuta una vez en
desarrollo, no en cada arranque del contenedor -- el resultado se versiona
en dashboard/static/audio/ding.wav.

Uso: python3 scripts/generate_ding.py
"""
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 16000
OUT_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "static" / "audio" / "ding.wav"

NOTES_HZ = [440, 554, 659, 880]
CADENCE_S = 2.0        # intervalo entre el inicio de cada nota
FULL_VOLUME_S = 1.0    # volumen pleno antes de empezar a apagarse
FADE_TAIL_S = 1.2      # duración del fade -- termina en 1.0 + 1.2 = 2.2s,
                        # 0.2s después de que ya haya arrancado la siguiente
                        # nota (cadencia 2s), de ahí el solape "tipo campana"
ATTACK_MS = 10          # fade-in cortísimo para evitar un click al empezar
AMPLITUDE = 9000        # deja margen de sobra bajo el máximo de int16 (32767)
                        # incluso sumando la cola de la nota anterior


def _note_envelope(n_samples: int) -> list[float]:
    attack_samples = int(SAMPLE_RATE * ATTACK_MS / 1000)
    full_samples = int(SAMPLE_RATE * FULL_VOLUME_S)
    fade_samples = int(SAMPLE_RATE * FADE_TAIL_S)
    env = []
    for i in range(n_samples):
        if i < attack_samples:
            env.append(i / attack_samples)
        elif i < full_samples:
            env.append(1.0)
        elif i < full_samples + fade_samples:
            env.append(1.0 - (i - full_samples) / fade_samples)
        else:
            env.append(0.0)
    return env


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    note_duration_s = FULL_VOLUME_S + FADE_TAIL_S
    note_samples = int(SAMPLE_RATE * note_duration_s)
    envelope = _note_envelope(note_samples)

    total_duration_s = CADENCE_S * (len(NOTES_HZ) - 1) + note_duration_s
    total_samples = int(SAMPLE_RATE * total_duration_s)
    buffer = [0.0] * total_samples

    for i, freq in enumerate(NOTES_HZ):
        onset = int(SAMPLE_RATE * CADENCE_S * i)
        for j in range(note_samples):
            idx = onset + j
            if idx >= total_samples:
                break
            buffer[idx] += envelope[j] * AMPLITUDE * math.sin(2 * math.pi * freq * j / SAMPLE_RATE)

    samples = [max(-32767, min(32767, int(round(s)))) for s in buffer]

    with wave.open(str(OUT_PATH), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    print(f"Generado {OUT_PATH} ({len(samples)/SAMPLE_RATE:.2f}s, notas: {NOTES_HZ})")


if __name__ == "__main__":
    main()
