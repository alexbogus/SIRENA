from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
import models.audit as audit_model
import models.speakers as speakers_model
import models.zones as zones_model
from routes.auth import login_required

bp = Blueprint("zones", __name__, url_prefix="/zones")
logger = config.get_logger("zones")

DEFAULT_VOLUME_PERCENT = 70


@bp.route("/")
@login_required
def index():
    zones = zones_model.list_all()
    for zone in zones:
        speakers = zones_model.speakers_for_zone(zone["id"])
        zone["speakers"] = speakers
        known_volumes = [sp["volume_percent"] for sp in speakers if sp["volume_percent"] is not None]
        zone["default_volume"] = (
            round(sum(known_volumes) / len(known_volumes)) if known_volumes else DEFAULT_VOLUME_PERCENT
        )
    return render_template("zones.html", zones=zones)


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
        audit_model.record("zone", "created", name)
        flash(f"Zona {name!r} creada.", "success")
    except Exception as exc:
        flash(f"No se pudo crear la zona: {exc}", "error")
    return redirect(url_for("zones.index"))


@bp.route("/<int:zone_id>/edit", methods=["POST"])
@login_required
def edit(zone_id: int):
    name = request.form.get("name", "").strip()
    if not name:
        flash("El nombre es obligatorio.", "error")
        return redirect(url_for("zones.index"))
    zone = zones_model.get(zone_id)
    try:
        zones_model.update(zone_id, name)
        logger.info(f"Zona {zone_id} renombrada: {zone['name'] if zone else zone_id!r} -> {name!r}")
        audit_model.record("zone", "updated", name,
                            f"nombre {zone['name'] if zone else '?'} -> {name}")
        flash("Zona actualizada.", "success")
    except Exception as exc:
        flash(f"No se pudo actualizar la zona: {exc}", "error")
    return redirect(url_for("zones.index"))


@bp.route("/<int:zone_id>/toggle", methods=["POST"])
@login_required
def toggle(zone_id: int):
    zone = zones_model.get(zone_id)
    if not zone:
        flash("La zona ya no existe.", "error")
        return redirect(url_for("zones.index"))
    new_enabled = not bool(zone["enabled"])
    zones_model.set_enabled(zone_id, new_enabled)
    logger.info(f"Zona {zone_id} ({zone['name']}) {'habilitada' if new_enabled else 'deshabilitada'}")
    audit_model.record("zone", "updated", zone["name"],
                        "habilitada" if new_enabled else "deshabilitada")
    flash(f"Zona {'habilitada' if new_enabled else 'deshabilitada'}.", "success")
    return redirect(url_for("zones.index"))


@bp.route("/<int:zone_id>/volume", methods=["POST"])
@login_required
def volume(zone_id: int):
    zone = zones_model.get(zone_id)
    if not zone:
        flash("La zona ya no existe.", "error")
        return redirect(url_for("zones.index"))

    try:
        volume_percent = int(request.form.get("volume_percent"))
    except (TypeError, ValueError):
        flash("El volumen debe ser un número entre 0 y 100.", "error")
        return redirect(url_for("zones.index"))
    volume_percent = max(0, min(100, volume_percent))

    speakers = [sp for sp in zones_model.speakers_for_zone(zone_id) if sp["enabled"]]
    if not speakers:
        flash(f"La zona {zone['name']!r} no tiene altavoces habilitados.", "error")
        return redirect(url_for("zones.index"))

    applied, failed = [], []
    for sp in speakers:
        if speakers_model.push_volume(sp, volume_percent):
            applied.append(sp["name"])
        else:
            failed.append(sp["name"])

    logger.info(f"Volumen de zona {zone['name']!r} ajustado a {volume_percent}%: "
                f"{len(applied)}/{len(speakers)} altavoces respondieron")
    audit_model.record("zone", "volume_set", zone["name"],
                        f"{volume_percent}% ({len(applied)}/{len(speakers)} altavoces)")

    if failed:
        flash(f"Volumen ajustado al {volume_percent}% en {len(applied)} altavoces. "
              f"No respondieron: {', '.join(failed)}.", "error")
    else:
        flash(f"Volumen ajustado al {volume_percent}% en {len(applied)} altavoces.", "success")
    return redirect(url_for("zones.index"))


@bp.route("/<int:zone_id>/delete", methods=["POST"])
@login_required
def delete(zone_id: int):
    zone = zones_model.get(zone_id)
    zones_model.delete(zone_id)
    logger.info(f"Zona {zone_id} eliminada")
    audit_model.record("zone", "deleted", zone["name"] if zone else str(zone_id))
    flash("Zona eliminada.", "success")
    return redirect(url_for("zones.index"))
