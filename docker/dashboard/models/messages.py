import config
from db import db_cursor


def create(source: str, text: str, speaker_ids: list[int], target_label: str,
           rule_id: int | None = None, incident_id: int | None = None,
           api_token_id: str | None = None, api_token_name: str | None = None) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO messages(source, text, target_label, rule_id, incident_id, "
            "api_token_id, api_token_name, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source, text, target_label, rule_id, incident_id,
             api_token_id, api_token_name, config.now_sql()),
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


def history_for_speaker(speaker_id: int, limit: int = 5) -> list[dict]:
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


def count_today() -> int:
    """Mensajes enviados hoy (hora local), para el resumen del panel."""
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE date(sent_at) = date('now', 'localtime')"
        ).fetchone()
    return row["c"]


def full_history(speaker_id: int | None = None, limit: int | None = None) -> list[dict]:
    """Histórico de mensajes enviados, para la página de histórico global
    (ordenable/buscable en el cliente). `speaker_id` filtra al histórico
    completo de un único altavoz (enlazado desde su card en el dashboard)."""
    query = """
        SELECT mt.id AS target_id, m.sent_at, m.source, m.target_label, m.text, m.api_token_name,
               mt.speaker_id, s.name AS speaker_name, mt.delivery_status
        FROM message_targets mt
        JOIN messages m ON m.id = mt.message_id
        JOIN speakers s ON s.id = mt.speaker_id
    """
    params: list = []
    if speaker_id is not None:
        query += " WHERE mt.speaker_id = ?"
        params.append(speaker_id)
    query += " ORDER BY m.sent_at DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    with db_cursor() as cur:
        rows = cur.execute(query, params).fetchall()
    return [
        {
            "target_id": r["target_id"],
            "sent_at": config.format_timestamp_es(r["sent_at"]),
            "source": r["source"],
            "api_token_name": r["api_token_name"],
            "speaker_id": r["speaker_id"],
            "speaker_name": r["speaker_name"],
            "target_label": r["target_label"] or "—",
            "text": r["text"],
            "delivery_status": r["delivery_status"],
        }
        for r in rows
    ]


def purge_older_than(cutoff_iso: str) -> int:
    with db_cursor() as cur:
        cur.execute("DELETE FROM messages WHERE sent_at < ?", (cutoff_iso,))
        return cur.rowcount  # message_targets se borra en cascada (ON DELETE CASCADE)


def delete_for_speaker(speaker_id: int) -> int:
    """Borra el histórico de mensajes de un altavoz concreto. Solo se
    elimina la fila de message_targets de ese altavoz: si el mensaje se
    envió también a otros altavoces/zonas, sigue existiendo para ellos."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM message_targets WHERE speaker_id = ?", (speaker_id,))
        return cur.rowcount


def delete_target(target_id: int) -> int:
    """Borra una única fila del histórico (un mensaje enviado a un altavoz
    concreto), sin afectar al mensaje para otros altavoces/zonas ni a sus
    logs de errores."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM message_targets WHERE id = ?", (target_id,))
        return cur.rowcount


def delete_all() -> int:
    """Borra todo el histórico de mensajes (todos los altavoces). Antes hay
    que desvincular processed_incidents.message_id: esa FK no tiene ON
    DELETE CASCADE (a diferencia de message_targets/message_queue), así que
    un DELETE directo violaría la constraint."""
    with db_cursor() as cur:
        cur.execute("UPDATE processed_incidents SET message_id = NULL WHERE message_id IS NOT NULL")
        cur.execute("DELETE FROM messages")  # message_targets/message_queue se borran en cascada
        return cur.rowcount
