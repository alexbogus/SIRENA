#!/usr/bin/env python3
"""Sirve un incidente.geojson fijo/parametrizable para probar el
cv112_poller sin depender del feed real. Valida que las peticiones traigan
los headers que exige el feed real (User-Agent/Referer/Accept) y devuelve
404 si no.

Uso: python3 fake_112cv_server.py --port 8200
Los incidentes a servir se leen de un JSON en memoria que se puede editar
en caliente vía POST /_set_features (facilita el test de dedupe: servir el
mismo id con distinta categoría en llamadas sucesivas).
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

_lock = threading.Lock()
_features: list[dict] = [
    {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[-0.5, 39.5], [-0.5, 39.51], [-0.49, 39.51], [-0.49, 39.5], [-0.5, 39.5]]]},
        "properties": {
            "id": 1,
            "description": {"es": "Incendio > Vegetación > Forestal", "va": "..."},
            "municipio": "Torrent",
            "direccion": None,
            "created": "2026-08-29T12:00:00",
        },
    }
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path != "/incidente.geojson":
            self.send_response(404)
            self.end_headers()
            return
        ua = self.headers.get("User-Agent", "")
        referer = self.headers.get("Referer", "")
        accept = self.headers.get("Accept", "")
        if "CECOM" not in ua and "Mozilla" not in ua:
            self.send_response(403)
            self.end_headers()
            return
        if "112cv.gva.es" not in referer:
            self.send_response(403)
            self.end_headers()
            return
        if "json" not in accept:
            self.send_response(403)
            self.end_headers()
            return
        with _lock:
            body = json.dumps({"type": "FeatureCollection", "features": _features}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/geo+json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/_set_features":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"[]")
        with _lock:
            global _features
            _features = payload
        self.send_response(200)
        self.end_headers()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8200)
    args = parser.parse_args()
    httpd = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"[fake_112cv_server] sirviendo en :{args.port}/incidente.geojson")
    print(f"[fake_112cv_server] POST /_set_features para cambiar los incidentes servidos")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
