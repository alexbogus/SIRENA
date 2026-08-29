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

El framing/Opus/colchón vive en _protocol_sender.py -- este script es solo
un CLI fino sobre ese módulo, que es también el que usa el servicio Docker
real (docker/dashboard/services/sender.py).
"""
import argparse
import socket

from _protocol_sender import load_pcm_chunks, ping, send_stream


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
