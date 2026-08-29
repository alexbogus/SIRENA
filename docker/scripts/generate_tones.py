#!/usr/bin/env python3
"""Genera los preámbulos sonoros (tonos) de las alertas: WAV sintéticos
propios del proyecto, sin copyright de terceros -- 16kHz/mono/16-bit, mismo
formato que exige _protocol_sender.load_pcm_chunks. Se ejecuta una vez en
desarrollo, no en cada arranque del contenedor -- el resultado se versiona
en dashboard/static/audio/tones/. Las filas de la tabla `tones` correspondientes
se siembran aparte, en db.py::init_db() (ver _DEFAULT_TONES).

Uso: python3 scripts/generate_tones.py
"""
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 16000
OUT_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "static" / "audio" / "tones"
AMPLITUDE = 9000  # margen de sobra bajo el máximo de int16 (32767)


def _envelope(n_samples: int, attack_ms: float, full_s: float, fade_s: float) -> list[float]:
    attack_samples = int(SAMPLE_RATE * attack_ms / 1000)
    full_samples = int(SAMPLE_RATE * full_s)
    fade_samples = int(SAMPLE_RATE * fade_s)
    env = []
    for i in range(n_samples):
        if i < attack_samples:
            env.append(i / attack_samples if attack_samples else 1.0)
        elif i < full_samples:
            env.append(1.0)
        elif i < full_samples + fade_samples:
            env.append(1.0 - (i - full_samples) / fade_samples)
        else:
            env.append(0.0)
    return env


def _write_wav(path: Path, buffer: list[float]) -> None:
    samples = [max(-32767, min(32767, int(round(s)))) for s in buffer]
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    print(f"Generado {path} ({len(samples)/SAMPLE_RATE:.2f}s)")


def generate_clasico(path: Path) -> None:
    """4 notas (440/554/659/880Hz) con cadencia lenta de 2s y solape tipo
    campana -- el ding original del proyecto."""
    notes_hz = [440, 554, 659, 880]
    cadence_s, full_s, fade_s = 2.0, 1.0, 1.2
    note_duration_s = full_s + fade_s
    note_samples = int(SAMPLE_RATE * note_duration_s)
    envelope = _envelope(note_samples, attack_ms=10, full_s=full_s, fade_s=fade_s)

    total_duration_s = cadence_s * (len(notes_hz) - 1) + note_duration_s
    total_samples = int(SAMPLE_RATE * total_duration_s)
    buffer = [0.0] * total_samples

    for i, freq in enumerate(notes_hz):
        onset = int(SAMPLE_RATE * cadence_s * i)
        for j in range(note_samples):
            idx = onset + j
            if idx >= total_samples:
                break
            buffer[idx] += envelope[j] * AMPLITUDE * math.sin(2 * math.pi * freq * j / SAMPLE_RATE)

    _write_wav(path, buffer)


def generate_urgente(path: Path) -> None:
    """Pitidos cortos y rápidos repetidos (tono de alerta urgente)."""
    freq = 1000
    beep_s, gap_s, repeats = 0.15, 0.1, 6
    beep_samples = int(SAMPLE_RATE * beep_s)
    gap_samples = int(SAMPLE_RATE * gap_s)
    envelope = _envelope(beep_samples, attack_ms=5, full_s=beep_s - 0.02, fade_s=0.02)

    total_samples = (beep_samples + gap_samples) * repeats
    buffer = [0.0] * total_samples

    for r in range(repeats):
        onset = r * (beep_samples + gap_samples)
        for j in range(beep_samples):
            buffer[onset + j] = envelope[j] * AMPLITUDE * math.sin(2 * math.pi * freq * j / SAMPLE_RATE)

    _write_wav(path, buffer)


def generate_suave(path: Path) -> None:
    """Un único tono largo y suave (aviso informativo)."""
    freq = 660
    duration_s, attack_ms, fade_s = 1.6, 150, 0.6
    n_samples = int(SAMPLE_RATE * duration_s)
    envelope = _envelope(n_samples, attack_ms=attack_ms, full_s=duration_s - fade_s, fade_s=fade_s)

    buffer = [envelope[j] * AMPLITUDE * math.sin(2 * math.pi * freq * j / SAMPLE_RATE) for j in range(n_samples)]
    _write_wav(path, buffer)


def generate_selectiva(path: Path) -> None:
    """Sirena tipo "wail": barrido continuo (sin silencios) entre ~1250Hz y
    ~2000Hz, periodo ~2.1s (grave sostenido ~1s, subida ~0.4s, agudo breve
    ~0.1s, bajada ~0.4s, resto del ciclo en grave). Frecuencias y cadencia
    medidas con un espectrograma (ffmpeg showspectrumpic) de una grabación
    real de la señal "selectiva" de protección civil aportada por el
    usuario -- una primera versión con pulsos aislados de tono fijo no se
    parecía nada al original porque el patrón real es un barrido continuo,
    no golpes sueltos. La fase se acumula muestra a muestra (en vez de
    sin(2*pi*f*t)) para que el barrido no tenga discontinuidades de fase."""
    f_lo, f_hi = 1250.0, 2000.0
    period_s = 2.1
    cycles = 2
    hold_lo_s, rise_s, hold_hi_s, fall_s = 1.0, 0.4, 0.1, 0.4
    rise_start_s = hold_lo_s
    rise_end_s = rise_start_s + rise_s
    hi_end_s = rise_end_s + hold_hi_s
    fall_end_s = hi_end_s + fall_s

    total_duration_s = period_s * cycles
    n_samples = int(SAMPLE_RATE * total_duration_s)
    fade_samples = int(SAMPLE_RATE * 0.015)  # 15ms, evita click en los bordes del archivo

    buffer = []
    phase = 0.0
    for i in range(n_samples):
        cycle_t = (i / SAMPLE_RATE) % period_s
        if cycle_t < rise_start_s:
            freq = f_lo
        elif cycle_t < rise_end_s:
            freq = f_lo + (f_hi - f_lo) * (cycle_t - rise_start_s) / rise_s
        elif cycle_t < hi_end_s:
            freq = f_hi
        elif cycle_t < fall_end_s:
            freq = f_hi - (f_hi - f_lo) * (cycle_t - hi_end_s) / fall_s
        else:
            freq = f_lo

        phase += 2 * math.pi * freq / SAMPLE_RATE
        sample = AMPLITUDE * math.sin(phase)
        if i < fade_samples:
            sample *= i / fade_samples
        elif i >= n_samples - fade_samples:
            sample *= (n_samples - i) / fade_samples
        buffer.append(sample)

    _write_wav(path, buffer)


def main():
    generate_clasico(OUT_DIR / "clasico.wav")
    generate_urgente(OUT_DIR / "urgente.wav")
    generate_suave(OUT_DIR / "suave.wav")
    generate_selectiva(OUT_DIR / "selectiva.wav")


if __name__ == "__main__":
    main()
