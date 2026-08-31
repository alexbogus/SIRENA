"""Envío de audio a altavoces reales, sobre el módulo compartido
_protocol_sender (docker/_protocol_sender.py) -- no reimplementa framing/Opus."""
import socket
import time
from concurrent.futures import ThreadPoolExecutor

import config
from _protocol_sender import load_pcm_chunks, ping, send_stream

logger = config.get_logger("sender")


def send_to_speaker(host: str, port: int, wav_path: str) -> bool:
    """Envía el WAV al altavoz. Devuelve True si el envío se completó sin
    excepción -- NO implica entrega confirmada, el protocolo no tiene ACK
    (ver services/delivery_confirmation.py)."""
    try:
        t0 = time.monotonic()
        chunks = load_pcm_chunks(wav_path)
        t_load = time.monotonic() - t0
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            t1 = time.monotonic()
            send_stream(sock, (host, port), chunks, quiet=True)
            t_stream = time.monotonic() - t1
        finally:
            sock.close()
        # t_stream incluye el colchón inicial + el ritmo real-time del resto
        # del stream (ver _protocol_sender.py) -- su duración es ~= la
        # duración del audio por diseño, no es "latencia" a optimizar.
        logger.info(
            f"Envío a {host}:{port}: carga PCM {t_load:.2f}s, "
            f"stream (Opus+UDP, ritmo real-time) {t_stream:.2f}s"
        )
        return True
    except Exception:
        logger.exception(f"Fallo enviando audio a {host}:{port}")
        return False


def send_to_many(targets: list[tuple[int, str, int]], wav_path: str) -> dict[int, bool]:
    """targets: lista de (speaker_id, host, port). Devuelve {speaker_id: send_ok}."""
    results: dict[int, bool] = {}
    if not targets:
        return results
    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as pool:
        futures = {
            pool.submit(send_to_speaker, host, port, wav_path): speaker_id
            for speaker_id, host, port in targets
        }
        for future in futures:
            speaker_id = futures[future]
            results[speaker_id] = future.result()
    return results


def check_ping(host: str, port: int, timeout: float = 2.0) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return ping(sock, (host, port), timeout=timeout)
    finally:
        sock.close()
