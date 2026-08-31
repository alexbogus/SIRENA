import datetime
from pathlib import Path

from flask import Blueprint, after_this_request, flash, redirect, render_template, request, send_file, url_for

import config
import models.message_templates as message_templates_model
import models.messages as messages_model
import models.settings as settings_model
import models.speaker_errors as speaker_errors_model
import models.speakers as speakers_model
import models.tones as tones_model
import models.zones as zones_model
from routes.auth import login_required
from routes.settings import _parse_voice_choice
from scheduler import scheduler
from services.delivery_confirmation import schedule_confirmations
from services.sender import send_to_many
from services.tts import build_alert_wav, build_preview_wav

bp = Blueprint("manual_send", __name__, url_prefix="/send")
logger = config.get_logger("manual_send")


@bp.route("/")
@login_required
def index():
    return render_template(
        "manual_send.html",
        zones=zones_model.list_all(),
        speakers=speakers_model.list_all(),
        tones=tones_model.list_enabled(),
        tts_voices=settings_model.tts_voices_choices(),
        templates=message_templates_model.list_all(),
    )


def _parse_tone_id() -> int | None:
    raw = request.form.get("tone_id", "").strip()
    return int(raw) if raw else None


def _parse_voice_override(raw: str) -> tuple[str | None, int | None]:
    """A diferencia de routes.settings._parse_voice_choice (que siempre
    resuelve a una voz del catálogo), aquí un valor vacío significa "no
    sobrescribir" -- se usa la voz por defecto de Configuración (ver
    settings.tts-preview-btn, que llama a este preview sin voice_choice)."""
    raw = raw.strip()
    if not raw:
        return None, None
    return _parse_voice_choice(raw)


@bp.route("/preview", methods=["POST"])
@login_required
def preview():
    text = request.form.get("text", "").strip()
    if not text:
        return {"error": "El texto no puede estar vacío."}, 400

    tone_id = _parse_tone_id()
    voice, speaker_id = _parse_voice_override(request.form.get("voice_choice", ""))
    try:
        repeats = int(request.form.get("repeats", 1))
    except (TypeError, ValueError):
        repeats = 1

    try:
        wav_path = build_preview_wav(
            text, tone_id=tone_id, voice=voice, speaker_id=speaker_id, repeats=repeats
        )
    except Exception:
        logger.exception("Fallo de síntesis TTS en preview")
        return {"error": "Fallo al generar el audio (Piper no responde)."}, 502

    @after_this_request
    def _cleanup(response):
        Path(wav_path).unlink(missing_ok=True)
        return response

    return send_file(wav_path, mimetype="audio/wav")


@bp.route("/", methods=["POST"])
@login_required
def send():
    text = request.form.get("text", "").strip()
    target = request.form.get("target")
    all_speakers = target == "all"
    zone_ids = [int(z) for z in request.form.getlist("zone_ids")] if target == "zones" else []
    speaker_ids = [int(s) for s in request.form.getlist("speaker_ids")] if target == "speakers" else []
    tone_id = _parse_tone_id()

    if not text:
        flash("El texto no puede estar vacío.", "error")
        return redirect(url_for("manual_send.index"))

    targets = speakers_model.resolve_targets(
        zone_ids=zone_ids, all_speakers=all_speakers, speaker_ids=speaker_ids
    )
    if not targets:
        flash("No hay altavoces en el destino seleccionado.", "error")
        return redirect(url_for("manual_send.index"))

    if all_speakers:
        target_label = "Todos"
    elif target == "speakers":
        speaker_names = [t["name"] for t in targets]
        target_label = ", ".join(speaker_names) if speaker_names else "—"
    else:
        zone_names = [z["name"] for z in zones_model.list_all() if z["id"] in zone_ids]
        target_label = ", ".join(zone_names) if zone_names else "—"

    try:
        wav_path = build_alert_wav(text, tone_id=tone_id)
    except Exception:
        logger.exception("Fallo de síntesis TTS en envío manual")
        flash("Fallo al generar el audio (Piper no responde). Inténtalo de nuevo.", "error")
        return redirect(url_for("manual_send.index"))

    target_speaker_ids = [t["id"] for t in targets]
    message_id = messages_model.create(source="manual", text=text, speaker_ids=target_speaker_ids,
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
