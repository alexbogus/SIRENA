"""Polling periódico de GET /status de cada altavoz. Cada altavoz en su
propio try/except: un altavoz caído no debe impedir consultar el resto."""
import datetime

import requests

import config
import models.speaker_errors as speaker_errors_model
import models.speakers as speakers_model

logger = config.get_logger("status_poller")


def poll_once() -> None:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for sp in speakers_model.list_all():
        was_ok = bool(sp.get("last_poll_ok"))
        try:
            resp = requests.get(f"http://{sp['ip']}/status", timeout=3)
            resp.raise_for_status()
            status = resp.json()
            speakers_model.upsert_status(sp["id"], status, poll_ok=True, poll_at=now)
            if not was_ok and sp.get("last_poll_at") is not None:
                # Solo se registra la recuperación si ya había un poll previo
                # (evita un falso "recuperado" en el primer poll tras un alta).
                speaker_errors_model.record(sp["id"], f"Altavoz {sp['name']!r} vuelve a responder")
        except Exception as exc:
            speakers_model.upsert_status(sp["id"], {}, poll_ok=False, poll_at=now)
            logger.warning(f"Altavoz {sp['name']!r} ({sp['ip']}) no responde a /status: {exc}")
            if was_ok or sp.get("last_poll_at") is None:
                # Se registra en la primera caída detectada (transición
                # online->offline, o el primer poll fallido tras el alta),
                # no en cada ciclo de 10s mientras siga caído -- evitaría
                # inundar el log de errores con la misma caída repetida.
                speaker_errors_model.record(sp["id"], f"Altavoz {sp['name']!r} ({sp['ip']}) deja de responder: {exc}")


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
