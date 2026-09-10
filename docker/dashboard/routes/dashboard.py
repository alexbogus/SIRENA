import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

import config
import models.audit as audit_model
import models.health as health_model
import models.messages as messages_model
import models.settings as settings_model
import models.speaker_errors as speaker_errors_model
import models.speakers as speakers_model
import models.zones as zones_model
from routes.auth import login_required

bp = Blueprint("dashboard", __name__)
logger = config.get_logger("dashboard")


def _speaker_view(sp: dict) -> dict:
    sp = dict(sp)
    last_message = messages_model.latest_for_speaker(sp["id"])
    sp["last_sent_message"] = last_message
    # Se considera offline si el último poll falló o si nunca se ha podido consultar.
    sp["online"] = bool(sp.get("last_poll_ok"))
    sp["history"] = messages_model.history_for_speaker(sp["id"])
    sp["errors"] = _format_errors(speaker_errors_model.recent_for_speaker(sp["id"], limit=10))
    return sp


def _format_errors(errors: list[dict]) -> list[dict]:
    return [{**e, "occurred_at": config.format_timestamp_es(e["occurred_at"])} for e in errors]


def _health_view() -> dict:
    health = health_model.get_all()
    result = {}
    for component in ("cv112_feed", "piper"):
        h = health.get(component, {})
        failures = h.get("consecutive_failures", 0) or 0
        result[component] = {
            "ok": failures < config.SYSTEM_HEALTH_FAILURE_THRESHOLD,
            "last_ok_at": h.get("last_ok_at"),
            "last_error_at": h.get("last_error_at"),
            "last_error_message": h.get("last_error_message"),
            "consecutive_failures": failures,
        }
    return result


@bp.route("/")
@login_required
def index():
    speakers = [_speaker_view(sp) for sp in speakers_model.list_all()]
    return render_template(
        "dashboard.html",
        speakers=speakers,
        health=_health_view(),
        auto_alerts_enabled=settings_model.auto_alerts_enabled(),
        zones_active=len(zones_model.list_enabled()),
        messages_today=messages_model.count_today(),
    )


@bp.route("/api/speakers/status")
@login_required
def api_speakers_status():
    speakers = [_speaker_view(sp) for sp in speakers_model.list_all()]
    return jsonify({
        "speakers": speakers,
        "health": _health_view(),
        "auto_alerts_enabled": settings_model.auto_alerts_enabled(),
        "zones_active": len(zones_model.list_enabled()),
        "messages_today": messages_model.count_today(),
        "recent_errors": _format_errors(speaker_errors_model.recent(limit=20)),
    })


@bp.route("/messages/history")
@login_required
def message_history():
    speaker_id = request.args.get("speaker_id", type=int)
    entries = messages_model.full_history(speaker_id=speaker_id, limit=500 if speaker_id else None)
    speaker = speakers_model.get(speaker_id) if speaker_id else None
    errors = _format_errors(speaker_errors_model.recent_for_speaker(speaker_id, limit=50)) if speaker_id else []
    return render_template("message_history.html", entries=entries, speaker_filter=speaker, errors=errors)


@bp.route("/messages/history/clear-all", methods=["POST"])
@login_required
def clear_all_messages():
    n_messages = messages_model.delete_all()
    logger.info(f"Histórico de mensajes borrado por completo: {n_messages} mensajes")
    audit_model.record("messages", "cleared_all", "todos los altavoces", f"mensajes={n_messages}")
    flash("Histórico de mensajes borrado.", "success")
    return redirect(request.referrer or url_for("dashboard.message_history"))


@bp.route("/messages/history/target/<int:target_id>/delete", methods=["POST"])
@login_required
def delete_message_target(target_id: int):
    n = messages_model.delete_target(target_id)
    if n:
        logger.info(f"Mensaje borrado del histórico (target_id={target_id})")
        audit_model.record("messages", "target_deleted", str(target_id))
        flash("Mensaje borrado.", "success")
    else:
        flash("El mensaje ya no existe.", "error")
    return redirect(request.referrer or url_for("dashboard.message_history"))


@bp.route("/errors/clear-all", methods=["POST"])
@login_required
def clear_all_errors():
    n_errors = speaker_errors_model.delete_all()
    logger.info(f"Errores de altavoz borrados por completo: {n_errors} errores")
    audit_model.record("speaker_errors", "cleared_all", "todos los altavoces", f"errores={n_errors}")
    flash("Errores recientes borrados.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))


@bp.route("/api/auto-alerts/toggle", methods=["POST"])
@login_required
def toggle_auto_alerts():
    enabled = not settings_model.auto_alerts_enabled()
    settings_model.set_auto_alerts_enabled(enabled)
    logger.info(f"Alertas automáticas {'activadas' if enabled else 'pausadas'} por {request.remote_addr}")
    return jsonify({"auto_alerts_enabled": enabled})
