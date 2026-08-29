"""Polling periódico de GET /status de cada altavoz. Cada altavoz en su
propio try/except: un altavoz caído no debe impedir consultar el resto."""
import datetime

import requests

import config
import models.speakers as speakers_model

logger = config.get_logger("status_poller")


def poll_once() -> None:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for sp in speakers_model.list_all():
        try:
            resp = requests.get(f"http://{sp['ip']}/status", timeout=3)
            resp.raise_for_status()
            status = resp.json()
            speakers_model.upsert_status(sp["id"], status, poll_ok=True, poll_at=now)
        except Exception as exc:
            speakers_model.upsert_status(sp["id"], {}, poll_ok=False, poll_at=now)
            logger.warning(f"Altavoz {sp['name']!r} ({sp['ip']}) no responde a /status: {exc}")


def fetch_status(ip: str) -> dict | None:
    """Consulta puntual de /status, usada por delivery_confirmation para
    verificar la entrega de un mensaje concreto."""
    try:
        resp = requests.get(f"http://{ip}/status", timeout=3)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning(f"No se pudo consultar /status de {ip} para confirmar entrega: {exc}")
        return None
