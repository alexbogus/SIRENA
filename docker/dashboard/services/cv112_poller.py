"""Poller del feed de incidentes del 112CV: dedupe de 3 estados, motor de
reglas, geocoding, TTS y envío. Ver Fase 5 del plan para el razonamiento
completo del dedupe (un incidente puede cambiar de categoría sin cambiar
de id mientras sigue abierto, así que "no anunciado todavía" se re-evalúa
en cada poll; "ya anunciado" es un estado terminal que nunca se re-envía)."""
import datetime
from pathlib import Path

import requests

import config
import models.health as health_model
import models.incidents as incidents_model
import models.messages as messages_model
import models.rules as rules_model
import models.settings as settings_model
import models.speakers as speakers_model
from services.alert_text import build_alert_text
from services.geocoding import polygon_centroid, reverse_geocode
from services.sender import send_to_many
from services.tts import build_alert_wav

logger = config.get_logger("cv112_poller")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CECOM/1.0)",
    "Referer": "https://wpr.112cv.gva.es/",
    "Accept": "application/json, */*",
}


def poll_once(scheduler=None) -> None:
    correlation_id = config.new_correlation_id()
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    now_sql = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        resp = requests.get(config.CV112_FEED_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        geojson = resp.json()
    except Exception as exc:
        failures = health_model.report_failure("cv112_feed", now_sql, str(exc))
        logger.error(
            f"Fallo al descargar el feed del 112CV ({failures} fallo(s) consecutivo(s)): {exc}",
            extra={"correlation_id": correlation_id},
        )
        return

    health_model.report_ok("cv112_feed", now_sql)
    features = geojson.get("features", [])
    logger.info(f"Feed descargado: {len(features)} incidentes activos", extra={"correlation_id": correlation_id})

    for feature in features:
        _process_feature(feature, now_iso, correlation_id, scheduler)


def _process_feature(feature: dict, now_iso: str, correlation_id: str, scheduler) -> None:
    props = feature.get("properties", {})
    incident_id = props.get("id")
    if incident_id is None:
        return

    record = incidents_model.get(incident_id)
    if incidents_model.is_announced(record):
        return  # estado terminal, nunca se re-evalúa ni re-envía

    raw_description = (props.get("description") or {}).get("es", "")
    municipio = props.get("municipio") or ""

    if record is not None and record["last_raw_description"] == raw_description:
        return  # ya evaluado con esta misma categoría, no hace falta repetir

    incidents_model.upsert_seen(incident_id, raw_description, municipio, now_iso)

    if not settings_model.auto_alerts_enabled():
        logger.info(
            f"Incidente {incident_id} visto pero alertas automáticas pausadas (killswitch)",
            extra={"correlation_id": correlation_id},
        )
        return

    category_path = [p.strip() for p in raw_description.split(">")] if raw_description else []
    rule = rules_model.find_first_match(municipio, category_path)
    if rule is None:
        return

    logger.info(
        f"Incidente {incident_id} ({raw_description!r} en {municipio!r}) matchea regla {rule['name']!r}",
        extra={"correlation_id": correlation_id},
    )
    _announce(incident_id, props, feature.get("geometry"), rule, correlation_id, scheduler)


def _announce(incident_id: int, props: dict, geometry: dict | None, rule: dict,
              correlation_id: str, scheduler) -> None:
    municipio = props.get("municipio") or ""
    raw_description = (props.get("description") or {}).get("es", "")

    street_ref = None
    if geometry and geometry.get("type") == "Polygon":
        try:
            lat, lon = polygon_centroid(geometry["coordinates"])
            street_ref = reverse_geocode(lat, lon)
        except Exception:
            logger.warning(f"No se pudo calcular centroide/geocoding del incidente {incident_id}",
                            extra={"correlation_id": correlation_id})

    text = build_alert_text(raw_description, municipio, street_ref)

    targets = speakers_model.resolve_targets(
        zone_ids=[rule["target_zone_id"]] if rule["target_zone_id"] else None,
        all_speakers=rule["target_zone_id"] is None,
    )
    if not targets:
        logger.warning(f"Regla {rule['name']!r} no resuelve a ningún altavoz, incidente {incident_id} sin enviar",
                        extra={"correlation_id": correlation_id})
        return

    try:
        wav_path = build_alert_wav(text)
    except Exception:
        logger.error(f"Fallo de síntesis TTS para el incidente {incident_id}, se reintentará en el siguiente poll",
                     extra={"correlation_id": correlation_id}, exc_info=True)
        return  # message_id sigue NULL: no es estado terminal, se reintenta

    speaker_ids = [t["id"] for t in targets]
    message_id = messages_model.create(
        source="auto_112cv", text=text, speaker_ids=speaker_ids, rule_id=rule["id"], incident_id=incident_id
    )
    sent_at = datetime.datetime.now().isoformat(timespec="seconds")

    send_results = send_to_many([(t["id"], t["ip"], t["port"]) for t in targets], wav_path)
    for speaker_id, ok in send_results.items():
        messages_model.set_send_result(message_id, speaker_id, ok)
    Path(wav_path).unlink(missing_ok=True)

    incidents_model.mark_announced(incident_id, rule["id"], message_id)
    logger.info(
        f"Alerta enviada para incidente {incident_id}: {len(targets)} altavoz(ces), texto={text!r}",
        extra={"correlation_id": correlation_id},
    )

    if scheduler is not None:
        from services.delivery_confirmation import schedule_confirmations
        schedule_confirmations(scheduler, message_id, sent_at)
