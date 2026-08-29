import datetime
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for

import config
import models.messages as messages_model
import models.speaker_errors as speaker_errors_model
import models.speakers as speakers_model
import models.zones as zones_model
from routes.auth import login_required
from scheduler import scheduler
from services.delivery_confirmation import schedule_confirmations
from services.sender import send_to_many
from services.tts import build_alert_wav

bp = Blueprint("manual_send", __name__, url_prefix="/send")
logger = config.get_logger("manual_send")


@bp.route("/")
@login_required
def index():
    return render_template("manual_send.html", zones=zones_model.list_all())


@bp.route("/", methods=["POST"])
@login_required
def send():
    text = request.form.get("text", "").strip()
    all_speakers = request.form.get("target") == "all"
    zone_ids = [int(z) for z in request.form.getlist("zone_ids")]

    if not text:
        flash("El texto no puede estar vacío.", "error")
        return redirect(url_for("manual_send.index"))

    targets = speakers_model.resolve_targets(zone_ids=zone_ids, all_speakers=all_speakers)
    if not targets:
        flash("No hay altavoces en el destino seleccionado.", "error")
        return redirect(url_for("manual_send.index"))

    if all_speakers:
        target_label = "Todos"
    else:
        zone_names = [z["name"] for z in zones_model.list_all() if z["id"] in zone_ids]
        target_label = ", ".join(zone_names) if zone_names else "—"

    try:
        wav_path = build_alert_wav(text)
    except Exception:
        logger.exception("Fallo de síntesis TTS en envío manual")
        flash("Fallo al generar el audio (Piper no responde). Inténtalo de nuevo.", "error")
        return redirect(url_for("manual_send.index"))

    speaker_ids = [t["id"] for t in targets]
    message_id = messages_model.create(source="manual", text=text, speaker_ids=speaker_ids,
                                        target_label=target_label)
    sent_at = datetime.datetime.now().isoformat(timespec="seconds")

    send_results = send_to_many([(t["id"], t["ip"], t["port"]) for t in targets], wav_path)
    for speaker_id, ok in send_results.items():
        messages_model.set_send_result(message_id, speaker_id, ok)
        if not ok:
            speaker_name = next((t["name"] for t in targets if t["id"] == speaker_id), speaker_id)
            speaker_errors_model.record(speaker_id, f"Fallo al enviar mensaje manual a {speaker_name!r}")
    Path(wav_path).unlink(missing_ok=True)

    schedule_confirmations(scheduler, message_id, sent_at)

    ok_count = sum(1 for v in send_results.values() if v)
    logger.info(f"Envío manual a {len(targets)} altavoz(ces), {ok_count} OK, texto={text!r}")
    flash(f"Enviado a {ok_count}/{len(targets)} altavoces, verificando entrega...", "success")
    return redirect(url_for("dashboard.index"))
