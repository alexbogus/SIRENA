#!/usr/bin/env python3
"""
Script de referencia (NO producción) para enviar audio a un altavoz
ip-speaker vía el protocolo UDP propio (ver esp32s3-firmware/ip-speaker/main/protocol.h).

Uso:
    python3 reference_send_audio.py --host 10.0.1.56 --wav /ruta/audio.wav
    python3 reference_send_audio.py --host 10.0.1.56 --wav audio.wav --simulate-loss 0.05

El WAV debe ser 16kHz, mono, 16-bit (el mismo formato que produce Piper).
Cada bloque de 20ms se codifica en Opus (requiere `pip install opuslib` y la
librería nativa libopus instalada, p.ej. `brew install opus` / `apt install
libopus0`) antes de enviarse -- el firmware, desde el Hito 4, espera frames
Opus en los paquetes AUDIO, no PCM crudo.

Aplica un colchón inicial de ~300ms antes de empezar el ritmo real-time,
imprescindible para no sufrir microcortes por jitter de red (ver Hito 1
del plan: un emisor sin colchón produce audio audiblemente cortado).
"""
import argparse
import random
import socket
import struct
import time
import wave

try:
    import opuslib
except ImportError:
    opuslib = None

PROTOCOL_MAGIC = 0x53504B31  # "SPK1"
PROTOCOL_VERSION = 1

FRAME_START = 1
FRAME_AUDIO = 2
FRAME_END = 3
FRAME_PING = 4
FRAME_PONG = 5

HEADER_FMT = "!IBBHII"  # magic, version, frame_type, reserved, seq_num, payload_len
HEADER_SIZE = struct.calcsize(HEADER_FMT)
assert HEADER_SIZE == 16

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 320  # 20ms a 16kHz
CHUNK_BYTES = CHUNK_SAMPLES * 2  # 16-bit mono
LEAD_CHUNKS = 15  # ~300ms de colchón inicial


def build_header(frame_type: int, seq_num: int, payload_len: int) -> bytes:
    return struct.pack(HEADER_FMT, PROTOCOL_MAGIC, PROTOCOL_VERSION, frame_type, 0, seq_num, payload_len)


def load_pcm_chunks(wav_path: str):
    with wave.open(wav_path, "rb") as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError(
                f"El WAV debe ser {SAMPLE_RATE}Hz mono 16-bit "
                f"(recibido: {w.getframerate()}Hz, {w.getnchannels()}ch, {w.getsampwidth()*8}bit)"
            )
        pcm = w.readframes(w.getnframes())
    return [pcm[i:i + CHUNK_BYTES] for i in range(0, len(pcm), CHUNK_BYTES)]


def make_opus_encoder():
    if opuslib is None:
        raise RuntimeError(
            "opuslib no está instalado. Ejecuta: pip install opuslib "
            "(y asegúrate de tener libopus instalada en el sistema)."
        )
    enc = opuslib.Encoder(SAMPLE_RATE, 1, opuslib.APPLICATION_VOIP)
    try:
        enc.bitrate = 24000  # bitrate típico de voz, ver Hito 4 del plan
    except Exception:
        pass  # algunas builds de opuslib fallan al fijar bitrate; se usa el de por defecto
    return enc


def send_stream(sock: socket.socket, dest, chunks, simulate_loss: float):
    encoder = make_opus_encoder()
    seq = 0

    sock.sendto(build_header(FRAME_START, seq, 0), dest)
    seq += 1

    def send_audio_chunk(pcm_chunk: bytes, seq_num: int):
        if simulate_loss > 0 and random.random() < simulate_loss:
            print(f"  [simulado] paquete seq={seq_num} descartado (no se envía)")
            return
        if len(pcm_chunk) < CHUNK_BYTES:
            pcm_chunk = pcm_chunk + b"\x00" * (CHUNK_BYTES - len(pcm_chunk))  # Opus exige el frame completo
        encoded = encoder.encode(pcm_chunk, CHUNK_SAMPLES)
        sock.sendto(build_header(FRAME_AUDIO, seq_num, len(encoded)) + encoded, dest)

    # Colchón inicial: los primeros LEAD_CHUNKS se envían sin esperar, para
    # que el ring buffer del ESP32 tenga margen antes de que empiece a
    # consumir datos (evita microcortes por jitter de red).
    lead = chunks[:LEAD_CHUNKS]
    rest = chunks[LEAD_CHUNKS:]
    for chunk in lead:
        send_audio_chunk(chunk, seq)
        seq += 1
        # Un burst totalmente sin pausa (0ms) llegó a saturar el receive
        # buffer del ESP32 en pruebas reales (10 de 17 paquetes iniciales
        # perdidos). Un espaciado mínimo de 2ms sigue siendo ~10x más rápido
        # que tiempo real pero no satura al receptor.
        time.sleep(0.002)

    t0 = time.time()
    for i, chunk in enumerate(rest):
        send_audio_chunk(chunk, seq)
        seq += 1
        target = t0 + (i + 1) * (CHUNK_BYTES / 2) / SAMPLE_RATE
        delay = target - time.time()
        if delay > 0:
            time.sleep(delay)

    sock.sendto(build_header(FRAME_END, seq, 0), dest)
    print(f"Stream enviado: {len(chunks)} bloques de audio, {seq + 1} paquetes en total")


def ping(sock: socket.socket, dest, timeout: float = 2.0) -> bool:
    sock.settimeout(timeout)
    sock.sendto(build_header(FRAME_PING, 0, 0), dest)
    try:
        data, _ = sock.recvfrom(HEADER_SIZE)
    except socket.timeout:
        return False
    if len(data) < HEADER_SIZE:
        return False
    magic, version, frame_type, _reserved, _seq, _plen = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
    return magic == PROTOCOL_MAGIC and version == PROTOCOL_VERSION and frame_type == FRAME_PONG


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="IP del altavoz")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--wav", help="Ruta a un WAV 16kHz/mono/16-bit a enviar")
    parser.add_argument("--ping", action="store_true", help="Solo hace un PING/PONG y sale")
    parser.add_argument("--simulate-loss", type=float, default=0.0,
                         help="Probabilidad (0-1) de descartar cada paquete AUDIO, para probar la robustez del protocolo")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.host, args.port)

    if args.ping:
        ok = ping(sock, dest)
        print("PONG recibido" if ok else "Sin respuesta (timeout)")
        return

    if not args.wav:
        parser.error("--wav es obligatorio salvo que uses --ping")

    chunks = load_pcm_chunks(args.wav)
    send_stream(sock, dest, chunks, args.simulate_loss)


if __name__ == "__main__":
    main()
