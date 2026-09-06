"""API REST para integraciones externas (n8n, etc.): sintetizar y emitir un
texto por megafonía, autenticado con un token de API (ver
services/api_tokens.py, gestionados desde /settings). Reutiliza el mismo
pipeline que el envío manual (services/alert_dispatch.py), con dos
diferencias: encola en vez de interrumpir si el altavoz está ocupado
(dispatch_with_queue), y respeta el alcance por zona del token."""
from flask import Blueprint, g, jsonify, request

import config
import models.speaker_errors as speaker_errors_model
import models.speakers as speakers_model
import models.tones as tones_model
import models.zones as zones_model
from routes.auth import require_api_token
from scheduler import scheduler
from services.alert_dispatch import dispatch_with_queue, resolve_names_to_ids

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
logger = config.get_logger("api_v1")


def _resolve_tone(data: dict) -> tuple[int | None, str | None]:
    tone_id = data.get("tone_id")
    tone_name = (data.get("tone_name") or "").strip()
    if tone_id or not tone_name:
        return tone_id, None
    ids, missing = resolve_names_to_ids([tone_name], tones_model.list_enabled())
    if missing:
        return None, f"Tono no encontrado: {missing[0]!r}."
    return ids[0], None


def _resolve_ids(data: dict, ids_key: str, names_key: str, catalog: list[dict], label: str) -> tuple[list[int], str | None]:
    ids = list(data.get(ids_key) or [])
    names = data.get(names_key) or []
    if names:
        found, missing = resolve_names_to_ids(names, catalog)
        if missing:
            return [], f"{label.capitalize()} no encontrado: {', '.join(missing)}."
        ids += found
    return ids, None


@bp.route("/announce", methods=["POST"])
@require_api_token
def announce():
    token = g.api_token  # {id, name, zone_ids}: zone_ids None = sin restricción
    data = request.get_json(silent=True) or {}

    text = (data.get("text") or "").strip()
    if not text:
        return {"error": "El campo 'text' no puede estar vacío."}, 400

    target = data.get("target")
    if target not in ("all", "zone", "speaker"):
        return {"error": "El campo 'target' debe ser 'all', 'zone' o 'speaker'."}, 400

    tone_id, tone_error = _resolve_tone(data)
    if tone_error:
        return {"error": tone_error}, 400

    zone_ids: list[int] = []
    speaker_ids: list[int] = []
    if target == "zone":
        zone_ids, zone_error = _resolve_ids(data, "zone_ids", "zone_names", zones_model.list_all(), "zona")
        if zone_error:
            return {"error": zone_error}, 400
    elif target == "speaker":
        speaker_ids, speaker_error = _resolve_ids(data, "speaker_ids", "speaker_names", speakers_model.list_all(), "altavoz")
        if speaker_error:
            return {"error": speaker_error}, 400

    allowed_zone_ids = token["zone_ids"]
    all_speakers = target == "all"

    if allowed_zone_ids is not None:
        if target == "all":
            all_speakers = False
            zone_ids = allowed_zone_ids
        elif target == "zone":
            out_of_scope = sorted(set(zone_ids) - set(allowed_zone_ids))
            if out_of_scope:
                speaker_errors_model.record(
                    None, f"Token {token['name']!r} intentó salir de su alcance (zonas {out_of_scope})")
                return {"error": "Zona fuera del alcance del token."}, 403
        else:  # target == "speaker"
            allowed_speaker_ids = {s["id"] for z in allowed_zone_ids for s in zones_model.speakers_for_zone(z)}
            out_of_scope = sorted(set(speaker_ids) - allowed_speaker_ids)
            if out_of_scope:
                speaker_errors_model.record(
                    None, f"Token {token['name']!r} intentó salir de su alcance (altavoces {out_of_scope})")
                return {"error": "Altavoz fuera del alcance del token."}, 403

    targets = speakers_model.resolve_targets(zone_ids=zone_ids, all_speakers=all_speakers, speaker_ids=speaker_ids)
    if not targets:
        return {"error": "No hay altavoces en el destino seleccionado."}, 400

    if all_speakers:
        target_label = "Todos"
    elif target == "speaker":
        target_label = ", ".join(t["name"] for t in targets)
    else:
        target_label = ", ".join(z["name"] for z in zones_model.list_all() if z["id"] in zone_ids) or "—"

    try:
        result = dispatch_with_queue(
            scheduler, text, targets, target_label, tone_id=tone_id,
            api_token_id=token["id"], api_token_name=token["name"],
        )
    except Exception:
        logger.exception(f"Fallo de síntesis TTS en /api/v1/announce (token {token['name']!r})")
        speaker_errors_model.record(None, f"Fallo Piper al sintetizar mensaje de API (token {token['name']!r})")
        return {"error": "Fallo al generar el audio (Piper no responde)."}, 502

    logger.info(f"API announce: token={token['name']!r}, {len(result['dispatched'])} enviados, "
                f"{len(result['queued'])} encolados, texto={text!r}")
    return jsonify(result), 200
