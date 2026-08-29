"""Confirmación de entrega por correlación temporal (no hay ACK real en el
protocolo). Tras enviar un mensaje, se reconsulta /status del altavoz unos
segundos después y se compara last_message_at con la ventana de envío.

LIMITACIÓN CONOCIDA (documentar también en la UI, junto al check ✓/✗): esto
es correlación temporal, no un ACK por mensaje -- dos envíos casi
simultáneos al mismo altavoz pueden dar un falso positivo cruzado."""
import datetime

import config
import models.messages as messages_model
from services.status_poller import fetch_status

logger = config.get_logger("delivery_confirmation")


def _parse_wall_clock(value: str | None) -> datetime.datetime | None:
    if not value or value == "null":
        return None
    try:
        return datetime.datetime.strptime(value, "%d/%m/%Y - %H:%M:%S")
    except ValueError:
        return None


def confirm_target(target_id: int, message_id: int, speaker_id: int, speaker_ip: str, sent_at: str) -> None:
    status = fetch_status(speaker_ip)
    checked_at = datetime.datetime.now().isoformat(timespec="seconds")

    if status is None:
        messages_model.set_delivery_status(target_id, "unconfirmed", checked_at)
        return

    reported_at = _parse_wall_clock(status.get("last_message_at"))
    sent_at_dt = datetime.datetime.fromisoformat(sent_at)

    if reported_at is not None and abs((reported_at - sent_at_dt).total_seconds()) <= config.DELIVERY_CONFIRMATION_MARGIN_S:
        messages_model.set_delivery_status(target_id, "confirmed", checked_at)
    else:
        messages_model.set_delivery_status(target_id, "unconfirmed", checked_at)
        logger.info(
            f"Entrega no confirmada para speaker_id={speaker_id}, message_id={message_id} "
            f"(reported_at={reported_at}, sent_at={sent_at_dt})"
        )


def schedule_confirmations(scheduler, message_id: int, sent_at: str) -> None:
    """Programa, con un pequeño delay, la verificación de entrega de todos
    los targets 'pending' de un mensaje recién enviado."""
    run_date = datetime.datetime.now() + datetime.timedelta(seconds=config.DELIVERY_CONFIRMATION_DELAY_S)
    for target in messages_model.targets_with_speaker(message_id):
        if target["delivery_status"] != "pending":
            continue
        scheduler.add_job(
            confirm_target,
            "date",
            run_date=run_date,
            args=[target["id"], message_id, target["speaker_id"], target["speaker_ip"], sent_at],
            id=f"confirm-{target['id']}",
            misfire_grace_time=60,
        )
