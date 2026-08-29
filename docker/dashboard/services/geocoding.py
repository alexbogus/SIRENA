"""Reverse geocoding contra Nominatim (OpenStreetMap) para obtener una
referencia de calle/camino cercana al centroide de un incidente. Nunca lanza
excepción -- degrada a None si falla, no debe bloquear nunca el envío de
una alerta (ver Fase 5/9 del plan)."""
import threading
import time

import requests

import config
from db import db_cursor

logger = config.get_logger("geocoding")

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "esp32s3-ip-speaker-net-cecom/1.0 (uso interno, base de Proteccion Civil)"
_MIN_INTERVAL_S = 1.0  # requisito de uso de Nominatim: max 1 req/s

_rate_lock = threading.Lock()
_last_request_ts = 0.0


def _cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 5)},{round(lon, 5)}"


def _cache_get(key: str) -> str | None:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT result_text FROM geocode_cache WHERE lat_lon_key = ?", (key,)
        ).fetchone()
    return row["result_text"] if row else None


def _cache_set(key: str, result_text: str | None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO geocode_cache(lat_lon_key, result_text) VALUES (?, ?) "
            "ON CONFLICT(lat_lon_key) DO UPDATE SET result_text = excluded.result_text",
            (key, result_text),
        )


def _respect_rate_limit() -> None:
    global _last_request_ts
    with _rate_lock:
        elapsed = time.monotonic() - _last_request_ts
        if elapsed < _MIN_INTERVAL_S:
            time.sleep(_MIN_INTERVAL_S - elapsed)
        _last_request_ts = time.monotonic()


def reverse_geocode(lat: float, lon: float) -> str | None:
    key = _cache_key(lat, lon)
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT result_text FROM geocode_cache WHERE lat_lon_key = ?", (key,)
        ).fetchone()
    if row is not None:
        return row["result_text"]

    result_text = None
    try:
        _respect_rate_limit()
        resp = requests.get(
            _NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 17},
            headers={"User-Agent": _USER_AGENT},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        address = data.get("address", {})
        result_text = address.get("road") or address.get("pedestrian") or address.get("hamlet")
    except Exception:
        logger.warning(f"Reverse geocoding falló para ({lat}, {lon}), se omite referencia de calle", exc_info=True)
        result_text = None

    _cache_set(key, result_text)
    return result_text


def polygon_centroid(coordinates) -> tuple[float, float]:
    """Centroide simple (media de vértices del anillo exterior) de un
    polígono GeoJSON. Suficiente para los hexágonos pequeños del feed del
    112CV, no hace falta una librería GIS. coordinates viene en (lon, lat)."""
    ring = coordinates[0]
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return sum(lats) / len(lats), sum(lons) / len(lons)
