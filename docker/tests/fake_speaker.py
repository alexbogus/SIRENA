#!/usr/bin/env python3
"""Simula un altavoz ip-speaker para poder probar el dashboard sin hardware
real: expone GET /status (con el mismo comportamiento -ya corregido- de
last_message_at que el firmware real) y un listener UDP que responde PONG a
PING y loguea START/AUDIO/END.

Uso: python3 fake_speaker.py --http-port 8100 --udp-port 8101
Se pueden levantar varias instancias en puertos distintos para simular
varios altavoces.
"""
import argparse
import datetime
import json
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PROTOCOL_MAGIC = 0x53504B31
PROTOCOL_VERSION = 1
FRAME_START, FRAME_AUDIO, FRAME_END, FRAME_PING, FRAME_PONG = 1, 2, 3, 4, 5
HEADER_FMT = "!IBBHII"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

state = {"streaming": False, "last_message_ms": None, "volume": 70}
start_time = time.monotonic()


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def udp_loop(port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    print(f"[fake_speaker] UDP escuchando en :{port}")
    while True:
        data, addr = sock.recvfrom(4096)
        if len(data) < HEADER_SIZE:
            continue
        magic, version, frame_type, _res, seq, plen = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
        if magic != PROTOCOL_MAGIC or version != PROTOCOL_VERSION:
            continue
        if frame_type == FRAME_PING:
            sock.sendto(struct.pack(HEADER_FMT, PROTOCOL_MAGIC, PROTOCOL_VERSION, FRAME_PONG, 0, 0, 0), addr)
        elif frame_type == FRAME_START:
            state["streaming"] = True
            state["last_message_ms"] = _now_ms()
            print(f"[fake_speaker] START seq={seq}")
        elif frame_type == FRAME_AUDIO:
            state["last_message_ms"] = _now_ms()
        elif frame_type == FRAME_END:
            state["streaming"] = False
            print(f"[fake_speaker] END seq={seq}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return
        last_message_at = None
        if state["last_message_ms"] is not None:
            ago_s = (_now_ms() - state["last_message_ms"]) / 1000
            event_time = datetime.datetime.now() - datetime.timedelta(seconds=ago_s)
            last_message_at = event_time.strftime("%d/%m/%Y - %H:%M:%S")
        body = json.dumps({
            "firmware_version": "fake-1.0.0",
            "ip": self.server.server_address[0] or "127.0.0.1",
            "rssi_dbm": -55,
            "state": "streaming" if state["streaming"] else "idle",
            "volume_percent": state["volume"],
            "last_message_at": last_message_at,  # None -> JSON null, igual que el firmware real
            "last_healthcheck_at": datetime.datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),
            "uptime_seconds": int(time.monotonic() - start_time),
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-port", type=int, default=8100)
    parser.add_argument("--udp-port", type=int, default=8101)
    args = parser.parse_args()

    threading.Thread(target=udp_loop, args=(args.udp_port,), daemon=True).start()
    httpd = HTTPServer(("0.0.0.0", args.http_port), Handler)
    print(f"[fake_speaker] HTTP /status en :{args.http_port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
