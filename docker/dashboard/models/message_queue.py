"""Cola de mensajes de la API pendientes de que su altavoz destino quede
libre. Ver services/alert_dispatch.py (encolado) y
services/queue_dispatcher.py (job periódico que los entrega o expira)."""
import config
from db import db_cursor


def enqueue(message_id: int, speaker_id: int, wav_path: str, expires_at: str) -> int:
    # enqueued_at explícito en hora local (config.now_sql()), no el
    # datetime('now') por defecto del esquema (SQLite lo evalúa en UTC) --
    # tiene que ser comparable con `expires_at`, que services/alert_dispatch.py
    # calcula con datetime.now() (hora local del servidor).
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO message_queue(message_id, speaker_id, wav_path, expires_at, enqueued_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (message_id, speaker_id, wav_path, expires_at, config.now_sql()),
        )
        return cur.lastrowid


def oldest_pending_per_speaker() -> list[dict]:
    """Una fila 'pending' por altavoz (la más antigua), para que el job de
    cola no dispare dos envíos al mismo altavoz en el mismo tick."""
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT mq.* FROM message_queue mq
            WHERE mq.status = 'pending'
            AND mq.id = (
                SELECT id FROM message_queue mq2
                WHERE mq2.speaker_id = mq.speaker_id AND mq2.status = 'pending'
                ORDER BY mq2.enqueued_at ASC LIMIT 1
            )
            """
        ).fetchall()
    return [dict(r) for r in rows]


def mark_sent(queue_id: int) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE message_queue SET status = 'sent', dispatched_at = datetime('now') WHERE id = ?",
            (queue_id,),
        )


def mark_expired(queue_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE message_queue SET status = 'expired' WHERE id = ?", (queue_id,))


def wav_still_referenced(wav_path: str) -> bool:
    """True si alguna otra fila 'pending' sigue apuntando al mismo WAV
    (varios altavoces ocupados del mismo mensaje comparten archivo) -- para
    no borrarlo mientras algún altavoz siga esperándolo."""
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT 1 FROM message_queue WHERE wav_path = ? AND status = 'pending' LIMIT 1",
            (wav_path,),
        ).fetchone()
    return row is not None
