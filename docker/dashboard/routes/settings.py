from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
import models.settings as settings_model
from routes.auth import login_required
from scheduler import scheduler

bp = Blueprint("settings", __name__, url_prefix="/settings")
logger = config.get_logger("settings")


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


@bp.route("/")
@login_required
def index():
    return render_template(
        "settings.html",
        cv112_poll_interval_s=settings_model.cv112_poll_interval_s(),
        status_poll_interval_s=settings_model.status_poll_interval_s(),
        db_log_retention_days=settings_model.db_log_retention_days(),
        dedupe_retention_days=settings_model.dedupe_retention_days(),
        min_poll=settings_model.MIN_POLL_INTERVAL_S,
        max_poll=settings_model.MAX_POLL_INTERVAL_S,
        min_retention=settings_model.MIN_RETENTION_DAYS,
        max_retention=settings_model.MAX_RETENTION_DAYS,
    )


@bp.route("/", methods=["POST"])
@login_required
def save():
    try:
        cv112_interval = _clamp(int(request.form.get("cv112_poll_interval_s", 45)),
                                 settings_model.MIN_POLL_INTERVAL_S, settings_model.MAX_POLL_INTERVAL_S)
        status_interval = _clamp(int(request.form.get("status_poll_interval_s", 10)),
                                  settings_model.MIN_POLL_INTERVAL_S, settings_model.MAX_POLL_INTERVAL_S)
        log_retention = _clamp(int(request.form.get("db_log_retention_days", 90)),
                                settings_model.MIN_RETENTION_DAYS, settings_model.MAX_RETENTION_DAYS)
        dedupe_retention = _clamp(int(request.form.get("dedupe_retention_days", 90)),
                                   settings_model.MIN_RETENTION_DAYS, settings_model.MAX_RETENTION_DAYS)
    except (TypeError, ValueError):
        flash("Valores inválidos.", "error")
        return redirect(url_for("settings.index"))

    settings_model.set("cv112_poll_interval_s", str(cv112_interval))
    settings_model.set("status_poll_interval_s", str(status_interval))
    settings_model.set("db_log_retention_days", str(log_retention))
    settings_model.set("dedupe_retention_days", str(dedupe_retention))

    _reschedule_poll_jobs(cv112_interval, status_interval)

    logger.info(
        f"Configuración actualizada: cv112_poll={cv112_interval}s, status_poll={status_interval}s, "
        f"log_retention={log_retention}d, dedupe_retention={dedupe_retention}d"
    )
    flash("Configuración guardada. Los nuevos intervalos ya están activos.", "success")
    return redirect(url_for("settings.index"))


def _reschedule_poll_jobs(cv112_interval: int, status_interval: int) -> None:
    """Aplica los nuevos intervalos sin reiniciar el proceso, reprogramando
    los jobs ya registrados en app.py (mismos ids: 'cv112_poller' y
    'status_poller')."""
    if scheduler.get_job("cv112_poller"):
        scheduler.reschedule_job("cv112_poller", trigger="interval", seconds=cv112_interval)
    if scheduler.get_job("status_poller"):
        scheduler.reschedule_job("status_poller", trigger="interval", seconds=status_interval)
