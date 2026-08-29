from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

import config
import models.settings as settings_model
import models.tones as tones_model
from routes.auth import login_required
from scheduler import scheduler

bp = Blueprint("settings", __name__, url_prefix="/settings")
logger = config.get_logger("settings")

TONES_DIR = config.BASE_DIR / "static" / "audio" / "tones"


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
        tones=tones_model.list_all(),
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


@bp.route("/tones/upload", methods=["POST"])
@login_required
def tones_upload():
    name = request.form.get("name", "").strip()
    file = request.files.get("file")

    if not name:
        flash("El nombre del tono es obligatorio.", "error")
        return redirect(url_for("settings.index"))
    if not file or not file.filename:
        flash("Selecciona un archivo .wav.", "error")
        return redirect(url_for("settings.index"))
    if not file.filename.lower().endswith(".wav"):
        flash("El archivo debe ser un .wav.", "error")
        return redirect(url_for("settings.index"))

    TONES_DIR.mkdir(parents=True, exist_ok=True)
    base = secure_filename(Path(file.filename).stem) or "tono"
    filename = f"{base}.wav"
    dest = TONES_DIR / filename
    suffix = 2
    while dest.exists():
        filename = f"{base}_{suffix}.wav"
        dest = TONES_DIR / filename
        suffix += 1

    file.save(dest)
    tones_model.create(name, filename)
    logger.info(f"Tono subido: {name!r} ({filename})")
    flash(f"Tono {name!r} añadido.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/tones/<int:tone_id>/toggle", methods=["POST"])
@login_required
def tones_toggle(tone_id: int):
    tone = tones_model.get(tone_id)
    if not tone:
        flash("Tono no encontrado.", "error")
        return redirect(url_for("settings.index"))
    if tone["enabled"] and tone["is_default"]:
        flash("No se puede deshabilitar el tono por defecto. Marca otro como por defecto primero.", "error")
        return redirect(url_for("settings.index"))
    tones_model.set_enabled(tone_id, not tone["enabled"])
    flash(f"Tono {'habilitado' if not tone['enabled'] else 'deshabilitado'}.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/tones/<int:tone_id>/default", methods=["POST"])
@login_required
def tones_default(tone_id: int):
    tone = tones_model.get(tone_id)
    if not tone:
        flash("Tono no encontrado.", "error")
        return redirect(url_for("settings.index"))
    if not tone["enabled"]:
        flash("Habilita el tono antes de marcarlo por defecto.", "error")
        return redirect(url_for("settings.index"))
    tones_model.set_default(tone_id)
    flash(f"{tone['name']!r} es ahora el tono por defecto.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/tones/<int:tone_id>/delete", methods=["POST"])
@login_required
def tones_delete(tone_id: int):
    tone = tones_model.get(tone_id)
    if not tone:
        flash("Tono no encontrado.", "error")
        return redirect(url_for("settings.index"))
    if tone["is_default"]:
        flash("No se puede eliminar el tono por defecto. Marca otro como por defecto primero.", "error")
        return redirect(url_for("settings.index"))
    (TONES_DIR / tone["filename"]).unlink(missing_ok=True)
    tones_model.delete(tone_id)
    logger.info(f"Tono eliminado: {tone['name']!r}")
    flash("Tono eliminado.", "success")
    return redirect(url_for("settings.index"))


def _reschedule_poll_jobs(cv112_interval: int, status_interval: int) -> None:
    """Aplica los nuevos intervalos sin reiniciar el proceso, reprogramando
    los jobs ya registrados en app.py (mismos ids: 'cv112_poller' y
    'status_poller')."""
    if scheduler.get_job("cv112_poller"):
        scheduler.reschedule_job("cv112_poller", trigger="interval", seconds=cv112_interval)
    if scheduler.get_job("status_poller"):
        scheduler.reschedule_job("status_poller", trigger="interval", seconds=status_interval)
