"""Auditoría de alta/edición/baja de altavoces y zonas. Ver Fase 9c del
plan: log retenido en BD (retención configurable), a diferencia de los
eventos del feed 112CV que no se auditan aquí."""
from db import db_cursor


def record(entity_type: str, action: str, entity_name: str, details: str | None = None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log(entity_type, action, entity_name, details) VALUES (?, ?, ?, ?)",
            (entity_type, action, entity_name, details),
        )


def recent(limit: int = 200) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM audit_log ORDER BY occurred_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def purge_older_than(cutoff_iso: str) -> int:
    with db_cursor() as cur:
        cur.execute("DELETE FROM audit_log WHERE occurred_at < ?", (cutoff_iso,))
        return cur.rowcount
