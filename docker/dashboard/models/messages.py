import config
from db import db_cursor


def create(source: str, text: str, speaker_ids: list[int], target_label: str,
           rule_id: int | None = None, incident_id: int | None = None) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO messages(source, text, target_label, rule_id, incident_id, sent_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source, text, target_label, rule_id, incident_id, config.now_sql()),
        )
        message_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO message_targets(message_id, speaker_id) VALUES (?, ?)",
            [(message_id, sid) for sid in speaker_ids],
        )
    return message_id


def set_send_result(message_id: int, speaker_id: int, send_ok: bool) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE message_targets SET send_ok = ? WHERE message_id = ? AND speaker_id = ?",
            (1 if send_ok else 0, message_id, speaker_id),
        )
        if not send_ok:
            cur.execute(
                "UPDATE message_targets SET delivery_status = 'unconfirmed' "
                "WHERE message_id = ? AND speaker_id = ?",
                (message_id, speaker_id),
            )


def pending_targets(message_id: int) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM message_targets WHERE message_id = ? AND delivery_status = 'pending'",
            (message_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_delivery_status(target_id: int, status: str, checked_at: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE message_targets SET delivery_status = ?, checked_at = ? WHERE id = ?",
            (status, checked_at, target_id),
        )


def get_message(message_id: int) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return dict(row) if row else None


def targets_with_speaker(message_id: int) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT mt.*, s.name AS speaker_name, s.ip AS speaker_ip
            FROM message_targets mt JOIN speakers s ON s.id = mt.speaker_id
            WHERE mt.message_id = ?
            """,
            (message_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_for_speaker(speaker_id: int) -> dict | None:
    """Último mensaje enviado al altavoz (source y estado de entrega), para
    pintarlo en la card del dashboard."""
    with db_cursor() as cur:
        row = cur.execute(
            """
            SELECT m.text, m.sent_at, m.source, mt.delivery_status
            FROM message_targets mt JOIN messages m ON m.id = mt.message_id
            WHERE mt.speaker_id = ?
            ORDER BY m.sent_at DESC LIMIT 1
            """,
            (speaker_id,),
        ).fetchone()
    return dict(row) if row else None


def recent(limit: int = 100) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM messages ORDER BY sent_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def history_for_speaker(speaker_id: int, limit: int = 20) -> list[dict]:
    """Histórico de mensajes enviados a un altavoz concreto, para la tabla
    ordenable bajo su card en el dashboard: fecha, zona (target_label
    fijado en el momento del envío) y texto."""
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT m.sent_at, m.target_label, m.text
            FROM message_targets mt JOIN messages m ON m.id = mt.message_id
            WHERE mt.speaker_id = ?
            ORDER BY m.sent_at DESC LIMIT ?
            """,
            (speaker_id, limit),
        ).fetchall()
    return [
        {
            "sent_at": config.format_timestamp_es(r["sent_at"]),
            "target_label": r["target_label"] or "—",
            "text": r["text"],
        }
        for r in rows
    ]


def purge_older_than(cutoff_iso: str) -> int:
    with db_cursor() as cur:
        cur.execute("DELETE FROM messages WHERE sent_at < ?", (cutoff_iso,))
        return cur.rowcount  # message_targets se borra en cascada (ON DELETE CASCADE)
