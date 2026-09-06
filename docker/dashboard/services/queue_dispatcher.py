"""Job periódico (ver app.py::_start_scheduler) que entrega los mensajes de
la API que quedaron en cola porque su altavoz destino estaba reproduciendo
algo (ver services/alert_dispatch.py::dispatch_with_queue). Un tick por
altavoz y por vuelta como mucho, para no disparar dos envíos seguidos al
mismo altavoz en el mismo ciclo."""
import datetime
from pathlib import Path

import config
import models.message_queue as message_queue_model
import models.messages as messages_model
import models.speaker_errors as speaker_errors_model
import models.speakers as speakers_model
from scheduler import scheduler
from services.delivery_confirmation import schedule_confirmation_for
from services.sender import send_to_speaker
from services.status_poller import fetch_status

logger = config.get_logger("queue_dispatcher")


def process_queue() -> None:
    now = datetime.datetime.now()
    for row in message_queue_model.oldest_pending_per_speaker():
        speaker = speakers_model.get(row["speaker_id"])
        if speaker is None:
            message_queue_model.mark_expired(row["id"])  # altavoz borrado mientras esperaba
            continue

        expires_at = datetime.datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
        if now > expires_at:
            message_queue_model.mark_expired(row["id"])
            speaker_errors_model.record(
                speaker["id"],
                f"Mensaje de API (id {row['message_id']}) expirado en cola sin que "
                f"{speaker['name']!r} quedara libre",
            )
            logger.warning(f"Mensaje {row['message_id']} expirado en cola para {speaker['name']!r}")
            _cleanup_wav_if_unreferenced(row["wav_path"])
            continue

        status = fetch_status(speaker["ip"])
        if status and status.get("state") == "streaming":
            continue  # sigue ocupado, se reintenta en el siguiente tick

        sent_at = now.isoformat(timespec="seconds")
        ok = send_to_speaker(speaker["ip"], speaker["port"], row["wav_path"])
        messages_model.set_send_result(row["message_id"], speaker["id"], ok)
        message_queue_model.mark_sent(row["id"])
        if not ok:
            speaker_errors_model.record(speaker["id"], f"Fallo al enviar mensaje de API en cola a {speaker['name']!r}")
        else:
            target = next(
                (t for t in messages_model.targets_with_speaker(row["message_id"])
                 if t["speaker_id"] == speaker["id"]),
                None,
            )
            if target:
                schedule_confirmation_for(scheduler, target["id"], row["message_id"],
                                           speaker["id"], speaker["ip"], sent_at)
        logger.info(f"Mensaje {row['message_id']} entregado desde la cola a {speaker['name']!r} (ok={ok})")
        _cleanup_wav_if_unreferenced(row["wav_path"])


def _cleanup_wav_if_unreferenced(wav_path: str) -> None:
    if not message_queue_model.wav_still_referenced(wav_path):
        Path(wav_path).unlink(missing_ok=True)
