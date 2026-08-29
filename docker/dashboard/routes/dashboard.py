import datetime

from flask import Blueprint, jsonify, render_template, request

import config
import models.health as health_model
import models.messages as messages_model
import models.settings as settings_model
import models.speakers as speakers_model
from routes.auth import login_required

bp = Blueprint("dashboard", __name__)
logger = config.get_logger("dashboard")


def _speaker_view(sp: dict) -> dict:
    sp = dict(sp)
    last_message = messages_model.latest_for_speaker(sp["id"])
    sp["last_sent_message"] = last_message
    # Se considera offline si el último poll falló o si nunca se ha podido consultar.
    sp["online"] = bool(sp.get("last_poll_ok"))
    return sp


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
    )


@bp.route("/api/speakers/status")
@login_required
def api_speakers_status():
    speakers = [_speaker_view(sp) for sp in speakers_model.list_all()]
    return jsonify({"speakers": speakers, "health": _health_view(),
                     "auto_alerts_enabled": settings_model.auto_alerts_enabled()})


@bp.route("/api/auto-alerts/toggle", methods=["POST"])
@login_required
def toggle_auto_alerts():
    enabled = not settings_model.auto_alerts_enabled()
    settings_model.set_auto_alerts_enabled(enabled)
    logger.info(f"Alertas automáticas {'activadas' if enabled else 'pausadas'} por {request.remote_addr}")
    return jsonify({"auto_alerts_enabled": enabled})
