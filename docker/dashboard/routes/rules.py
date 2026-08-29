from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
import models.incidents as incidents_model
import models.rules as rules_model
import models.zones as zones_model
from routes.auth import login_required

bp = Blueprint("rules", __name__, url_prefix="/rules")
logger = config.get_logger("rules")


@bp.route("/")
@login_required
def index():
    return render_template(
        "rules.html",
        rules=rules_model.list_all(),
        zones=zones_model.list_all(),
        municipios=incidents_model.distinct_municipios(),
        category_paths=incidents_model.distinct_category_paths(),
    )


@bp.route("/", methods=["POST"])
@login_required
def create():
    _save(None)
    return redirect(url_for("rules.index"))


@bp.route("/<int:rule_id>/edit", methods=["POST"])
@login_required
def edit(rule_id: int):
    _save(rule_id)
    return redirect(url_for("rules.index"))


def _save(rule_id: int | None) -> None:
    name = request.form.get("name", "").strip()
    municipios = [m.strip() for m in request.form.getlist("municipios") if m.strip()]
    categorias_raw = request.form.getlist("categorias")  # cada valor "Incendio>Vegetación"
    categorias = [c.split(">") for c in categorias_raw if c.strip()]
    target_zone_raw = request.form.get("target_zone_id", "")
    target_zone_id = int(target_zone_raw) if target_zone_raw else None
    enabled = request.form.get("enabled") == "on"

    if not name:
        flash("El nombre de la regla es obligatorio.", "error")
        return

    if rule_id is None:
        rules_model.create(name, municipios, categorias, target_zone_id, enabled)
        logger.info(f"Regla de alerta creada: {name!r}")
        flash(f"Regla {name!r} creada.", "success")
    else:
        rules_model.update(rule_id, name, municipios, categorias, target_zone_id, enabled)
        logger.info(f"Regla de alerta {rule_id} actualizada: {name!r}")
        flash("Regla actualizada.", "success")


@bp.route("/<int:rule_id>/delete", methods=["POST"])
@login_required
def delete(rule_id: int):
    rules_model.delete(rule_id)
    logger.info(f"Regla de alerta {rule_id} eliminada")
    flash("Regla eliminada.", "success")
    return redirect(url_for("rules.index"))


@bp.route("/log")
@login_required
def log():
    return render_template("alert_log.html", entries=incidents_model.recent_log())
