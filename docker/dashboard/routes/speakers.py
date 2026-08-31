import requests
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

import config
import models.audit as audit_model
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
    description = request.form.get("description", "").strip() or None
    if not name or not ip:
        flash("Nombre e IP son obligatorios.", "error")
        return redirect(url_for("speakers.index"))
    try:
        speakers_model.create(name, ip, port, zone_ids, description)
        logger.info(f"Altavoz creado: {name} ({ip}:{port})")
        audit_model.record("speaker", "created", name, f"ip={ip} port={port}")
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
    description = request.form.get("description", "").strip() or None
    before = speakers_model.get(speaker_id)
    try:
        speakers_model.update(speaker_id, name, ip, port, zone_ids, description)
        logger.info(f"Altavoz {speaker_id} actualizado: {name} ({ip}:{port})")
        details = f"ip={before['ip'] if before else '?'}->{ip} port={before['port'] if before else '?'}->{port}"
        audit_model.record("speaker", "updated", name, details)
        flash("Altavoz actualizado.", "success")
    except Exception as exc:
        flash(f"No se pudo actualizar el altavoz: {exc}", "error")
    return redirect(url_for("speakers.index"))


@bp.route("/<int:speaker_id>/volume", methods=["POST"])
@login_required
def set_volume(speaker_id: int):
    sp = speakers_model.get(speaker_id)
    if not sp:
        return jsonify({"ok": False, "error": "Altavoz no encontrado"}), 404

    try:
        volume_percent = int((request.get_json(silent=True) or {}).get("volume_percent"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "volume_percent inválido"}), 400
    volume_percent = max(0, min(100, volume_percent))

    try:
        resp = requests.post(f"http://{sp['ip']}/volume", json={"volume_percent": volume_percent}, timeout=3)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning(f"No se pudo fijar el volumen de {sp['name']!r} ({sp['ip']}): {exc}")
        return jsonify({"ok": False, "error": "El altavoz no responde"}), 502

    speakers_model.set_volume(speaker_id, volume_percent)
    return jsonify({"ok": True, "volume_percent": volume_percent})


@bp.route("/<int:speaker_id>/toggle", methods=["POST"])
@login_required
def toggle(speaker_id: int):
    sp = speakers_model.get(speaker_id)
    if not sp:
        flash("El altavoz ya no existe.", "error")
        return redirect(url_for("speakers.index"))
    new_enabled = not bool(sp["enabled"])
    speakers_model.set_enabled(speaker_id, new_enabled)
    logger.info(f"Altavoz {speaker_id} ({sp['name']}) {'habilitado' if new_enabled else 'deshabilitado'}")
    audit_model.record("speaker", "updated", sp["name"],
                        "habilitado" if new_enabled else "deshabilitado")
    flash(f"Altavoz {'habilitado' if new_enabled else 'deshabilitado'}.", "success")
    return redirect(url_for("speakers.index"))


@bp.route("/<int:speaker_id>/delete", methods=["POST"])
@login_required
def delete(speaker_id: int):
    sp = speakers_model.get(speaker_id)
    speakers_model.delete(speaker_id)
    logger.info(f"Altavoz {speaker_id} eliminado")
    audit_model.record("speaker", "deleted", sp["name"] if sp else str(speaker_id),
                        f"ip={sp['ip']}" if sp else None)
    flash("Altavoz eliminado.", "success")
    return redirect(url_for("speakers.index"))
