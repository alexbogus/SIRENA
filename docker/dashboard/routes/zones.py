from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
import models.zones as zones_model
from routes.auth import login_required

bp = Blueprint("zones", __name__, url_prefix="/zones")
logger = config.get_logger("zones")


@bp.route("/")
@login_required
def index():
    return render_template("zones.html", zones=zones_model.list_all())


@bp.route("/", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    if not name:
        flash("El nombre es obligatorio.", "error")
        return redirect(url_for("zones.index"))
    try:
        zones_model.create(name)
        logger.info(f"Zona creada: {name}")
        flash(f"Zona {name!r} creada.", "success")
    except Exception as exc:
        flash(f"No se pudo crear la zona: {exc}", "error")
    return redirect(url_for("zones.index"))


@bp.route("/<int:zone_id>/delete", methods=["POST"])
@login_required
def delete(zone_id: int):
    zones_model.delete(zone_id)
    logger.info(f"Zona {zone_id} eliminada")
    flash("Zona eliminada.", "success")
    return redirect(url_for("zones.index"))
