from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
import models.speakers as speakers_model
import models.zones as zones_model
from routes.auth import login_required

bp = Blueprint("speakers", __name__, url_prefix="/speakers")
logger = config.get_logger("speakers")


@bp.route("/")
@login_required
def index():
    return render_template("speakers.html", speakers=speakers_model.list_all(), zones=zones_model.list_all())


@bp.route("/", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    ip = request.form.get("ip", "").strip()
    port = int(request.form.get("port") or 5005)
    zone_ids = [int(z) for z in request.form.getlist("zone_ids")]
    if not name or not ip:
        flash("Nombre e IP son obligatorios.", "error")
        return redirect(url_for("speakers.index"))
    try:
        speakers_model.create(name, ip, port, zone_ids)
        logger.info(f"Altavoz creado: {name} ({ip}:{port})")
        flash(f"Altavoz {name!r} añadido.", "success")
    except Exception as exc:
        flash(f"No se pudo crear el altavoz: {exc}", "error")
    return redirect(url_for("speakers.index"))


@bp.route("/<int:speaker_id>/edit", methods=["POST"])
@login_required
def edit(speaker_id: int):
    name = request.form.get("name", "").strip()
    ip = request.form.get("ip", "").strip()
    port = int(request.form.get("port") or 5005)
    zone_ids = [int(z) for z in request.form.getlist("zone_ids")]
    try:
        speakers_model.update(speaker_id, name, ip, port, zone_ids)
        logger.info(f"Altavoz {speaker_id} actualizado: {name} ({ip}:{port})")
        flash("Altavoz actualizado.", "success")
    except Exception as exc:
        flash(f"No se pudo actualizar el altavoz: {exc}", "error")
    return redirect(url_for("speakers.index"))


@bp.route("/<int:speaker_id>/delete", methods=["POST"])
@login_required
def delete(speaker_id: int):
    speakers_model.delete(speaker_id)
    logger.info(f"Altavoz {speaker_id} eliminado")
    flash("Altavoz eliminado.", "success")
    return redirect(url_for("speakers.index"))
