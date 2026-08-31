"""Log de errores de altavoz retenido en BD (caídas detectadas por polling,
fallos de envío). Ver Fase 9c del plan."""
from db import db_cursor


def record(speaker_id: int | None, message: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO speaker_error_log(speaker_id, message) VALUES (?, ?)",
            (speaker_id, message),
        )


def recent_for_speaker(speaker_id: int, limit: int = 20) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM speaker_error_log WHERE speaker_id = ? ORDER BY occurred_at DESC LIMIT ?",
            (speaker_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def recent(limit: int = 200) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT sel.*, s.name AS speaker_name FROM speaker_error_log sel
            LEFT JOIN speakers s ON s.id = sel.speaker_id
            ORDER BY sel.occurred_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def purge_older_than(cutoff_iso: str) -> int:
    with db_cursor() as cur:
        cur.execute("DELETE FROM speaker_error_log WHERE occurred_at < ?", (cutoff_iso,))
        return cur.rowcount


def delete_for_speaker(speaker_id: int) -> int:
    with db_cursor() as cur:
        cur.execute("DELETE FROM speaker_error_log WHERE speaker_id = ?", (speaker_id,))
        return cur.rowcount
