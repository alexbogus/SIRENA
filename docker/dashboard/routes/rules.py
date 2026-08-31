from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
import models.incidents as incidents_model
import models.rules as rules_model
import models.taxonomy as taxonomy_model
import models.tones as tones_model
import models.zones as zones_model
from routes.auth import login_required
from scheduler import scheduler
from services.cv112_poller import poll_once as cv112_poll_once

bp = Blueprint("rules", __name__, url_prefix="/rules")
logger = config.get_logger("rules")


@bp.route("/")
@login_required
def index():
    return render_template(
        "rules.html",
        rules=rules_model.list_all(),
        zones=zones_model.list_all(),
        tones=tones_model.list_enabled(),
        municipios=taxonomy_model.all_municipios(),
        category_paths=taxonomy_model.all_category_paths(),
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
    tone_raw = request.form.get("tone_id", "")
    tone_id = int(tone_raw) if tone_raw else None
    enabled = request.form.get("enabled") == "on"

    if not name:
        flash("El nombre de la regla es obligatorio.", "error")
        return

    if rule_id is None:
        rules_model.create(name, municipios, categorias, target_zone_id, tone_id, enabled)
        logger.info(f"Regla de alerta creada: {name!r}")
        flash(f"Regla {name!r} creada.", "success")
    else:
        rules_model.update(rule_id, name, municipios, categorias, target_zone_id, tone_id, enabled)
        logger.info(f"Regla de alerta {rule_id} actualizada: {name!r}")
        flash("Regla actualizada.", "success")


@bp.route("/rescan", methods=["POST"])
@login_required
def rescan():
    before_municipios = set(taxonomy_model.all_municipios())
    before_categorias = {tuple(c) for c in taxonomy_model.all_category_paths()}

    try:
        cv112_poll_once(scheduler)
    except Exception:
        logger.exception("Fallo al forzar el re-escaneo del feed 112CV")
        flash("No se pudo contactar con el feed del 112CV. Revisa los logs.", "error")
        return redirect(url_for("rules.index"))

    new_municipios = set(taxonomy_model.all_municipios()) - before_municipios
    new_categorias = {tuple(c) for c in taxonomy_model.all_category_paths()} - before_categorias

    if new_municipios or new_categorias:
        parts = []
        if new_municipios:
            parts.append(f"{len(new_municipios)} municipio(s) nuevo(s): {', '.join(sorted(new_municipios))}")
        if new_categorias:
            parts.append(f"{len(new_categorias)} categoría(s) nueva(s)")
        flash("Re-escaneo completado. " + "; ".join(parts) + ".", "success")
    else:
        flash("Re-escaneo completado. No hay municipios ni categorías nuevas en el feed actual.", "success")
    return redirect(url_for("rules.index"))


@bp.route("/municipios", methods=["POST"])
@login_required
def add_municipio():
    nombre = request.form.get("municipio", "").strip()
    if not nombre:
        flash("Escribe el nombre del municipio.", "error")
    elif taxonomy_model.is_known_municipio(nombre):
        flash(f"{nombre!r} ya está en la lista (o coincide con una variante existente).", "error")
    else:
        taxonomy_model.remember_municipio(nombre, source="manual")
        logger.info(f"Municipio añadido a mano: {nombre!r}")
        flash(f"Municipio {nombre!r} añadido.", "success")
    return redirect(url_for("rules.index"))


@bp.route("/<int:rule_id>/toggle", methods=["POST"])
@login_required
def toggle(rule_id: int):
    rule = rules_model.get(rule_id)
    if not rule:
        flash("La regla ya no existe.", "error")
        return redirect(url_for("rules.index"))
    new_enabled = not bool(rule["enabled"])
    rules_model.set_enabled(rule_id, new_enabled)
    logger.info(f"Regla de alerta {rule_id} ({rule['name']}) {'habilitada' if new_enabled else 'deshabilitada'}")
    flash(f"Regla {'habilitada' if new_enabled else 'deshabilitada'}.", "success")
    return redirect(url_for("rules.index"))


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
