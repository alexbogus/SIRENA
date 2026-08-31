import subprocess
import tempfile
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

import config
import models.message_templates as message_templates_model
import models.settings as settings_model
import models.tones as tones_model
import services.audio_convert as audio_convert
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
        templates=message_templates_model.list_all(),
        tts_voice=settings_model.tts_voice(),
        tts_speaker_id=settings_model.tts_speaker_id(),
        tts_length_scale=settings_model.tts_length_scale(),
        tts_expressiveness=settings_model.tts_noise_scale(),
        tts_sentence_silence=settings_model.tts_sentence_silence(),
        tts_voices=settings_model.TTS_VOICES,
        min_length_scale=settings_model.MIN_TTS_LENGTH_SCALE,
        max_length_scale=settings_model.MAX_TTS_LENGTH_SCALE,
        min_expressiveness=settings_model.MIN_TTS_NOISE,
        max_expressiveness=settings_model.MAX_TTS_NOISE,
        min_sentence_silence=settings_model.MIN_TTS_SENTENCE_SILENCE,
        max_sentence_silence=settings_model.MAX_TTS_SENTENCE_SILENCE,
    )


def _parse_voice_choice(raw: str) -> tuple[str, int | None]:
    """"filename|speaker_id" (speaker_id vacío = modelo de un solo locutor)
    -> (filename, speaker_id). El valor viene de un <select> cuyas opciones
    se generan desde settings_model.TTS_VOICES, así que se asume bien
    formado; si no lo está, cae al primer valor del catálogo."""
    filename, _, speaker_raw = raw.partition("|")
    if filename not in {v["filename"] for v in settings_model.TTS_VOICES}:
        default = settings_model.TTS_VOICES[0]
        return default["filename"], default["speaker_id"]
    return filename, int(speaker_raw) if speaker_raw else None


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
        tts_voice, tts_speaker_id = _parse_voice_choice(request.form.get("tts_voice_choice", ""))
        tts_length_scale = _clamp(float(request.form.get("tts_length_scale", 1.0)),
                                   settings_model.MIN_TTS_LENGTH_SCALE, settings_model.MAX_TTS_LENGTH_SCALE)
        tts_expressiveness = _clamp(float(request.form.get("tts_expressiveness", 0.75)),
                                     settings_model.MIN_TTS_NOISE, settings_model.MAX_TTS_NOISE)
        tts_sentence_silence = _clamp(float(request.form.get("tts_sentence_silence", 0.3)),
                                       settings_model.MIN_TTS_SENTENCE_SILENCE,
                                       settings_model.MAX_TTS_SENTENCE_SILENCE)
    except (TypeError, ValueError):
        flash("Valores inválidos.", "error")
        return redirect(url_for("settings.index"))

    settings_model.set("cv112_poll_interval_s", str(cv112_interval))
    settings_model.set("status_poll_interval_s", str(status_interval))
    settings_model.set("db_log_retention_days", str(log_retention))
    settings_model.set("dedupe_retention_days", str(dedupe_retention))
    settings_model.set("tts_voice", tts_voice)
    settings_model.set("tts_speaker_id", str(tts_speaker_id) if tts_speaker_id is not None else "")
    settings_model.set("tts_length_scale", str(tts_length_scale))
    settings_model.set("tts_noise_scale", str(tts_expressiveness))
    settings_model.set("tts_noise_w", str(tts_expressiveness))
    settings_model.set("tts_sentence_silence", str(tts_sentence_silence))

    _reschedule_poll_jobs(cv112_interval, status_interval)

    logger.info(
        f"Configuración actualizada: cv112_poll={cv112_interval}s, status_poll={status_interval}s, "
        f"log_retention={log_retention}d, dedupe_retention={dedupe_retention}d, "
        f"tts_voice={tts_voice}, tts_speaker_id={tts_speaker_id}"
    )
    flash("Configuración guardada. Los nuevos intervalos y la voz ya están activos.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/tones/upload", methods=["POST"])
@login_required
def tones_upload():
    name = request.form.get("name", "").strip()
    file = request.files.get("file")
    allowed_ext = (".wav", ".mp3")

    if not name:
        flash("El nombre del tono es obligatorio.", "error")
        return redirect(url_for("settings.index"))
    if not file or not file.filename:
        flash("Selecciona un archivo de audio (.wav o .mp3).", "error")
        return redirect(url_for("settings.index"))
    if not file.filename.lower().endswith(allowed_ext):
        flash("El archivo debe ser .wav o .mp3.", "error")
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

    src_suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=src_suffix, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    try:
        audio_convert.normalize_to_tone_wav(tmp_path, str(dest))
    except subprocess.CalledProcessError:
        flash("No se pudo procesar el archivo: formato de audio no válido o corrupto.", "error")
        return redirect(url_for("settings.index"))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

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


@bp.route("/templates/create", methods=["POST"])
@login_required
def templates_create():
    name = request.form.get("name", "").strip()
    text = request.form.get("text", "").strip()

    if not name or not text:
        flash("Nombre y texto son obligatorios.", "error")
        return redirect(url_for("settings.index"))

    message_templates_model.create(name, text)
    logger.info(f"Plantilla creada: {name!r}")
    flash(f"Plantilla {name!r} añadida.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/templates/<int:template_id>/delete", methods=["POST"])
@login_required
def templates_delete(template_id: int):
    template = message_templates_model.get(template_id)
    if not template:
        flash("Plantilla no encontrada.", "error")
        return redirect(url_for("settings.index"))
    message_templates_model.delete(template_id)
    logger.info(f"Plantilla eliminada: {template['name']!r}")
    flash("Plantilla eliminada.", "success")
    return redirect(url_for("settings.index"))


def _reschedule_poll_jobs(cv112_interval: int, status_interval: int) -> None:
    """Aplica los nuevos intervalos sin reiniciar el proceso, reprogramando
    los jobs ya registrados en app.py (mismos ids: 'cv112_poller' y
    'status_poller')."""
    if scheduler.get_job("cv112_poller"):
        scheduler.reschedule_job("cv112_poller", trigger="interval", seconds=cv112_interval)
    if scheduler.get_job("status_poller"):
        scheduler.reschedule_job("status_poller", trigger="interval", seconds=status_interval)
