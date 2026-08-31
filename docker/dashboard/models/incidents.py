"""Dedupe de incidentes del 112CV con 3 estados: nunca visto / visto-pero-no-
anunciado-todavía / ya-anunciado (estado terminal). Ver Fase 5 del plan --
un incidente puede cambiar de categoría mientras sigue abierto sin cambiar
de id, así que "no anunciado todavía" se re-evalúa en cada poll."""
import config
from db import db_cursor


def get(incident_id: int) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT * FROM processed_incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
    return dict(row) if row else None


def is_announced(record: dict) -> bool:
    return record is not None and record["message_id"] is not None


def upsert_seen(incident_id: int, raw_description: str, municipio: str, now: str) -> None:
    """Registra un incidente nunca visto, o actualiza last_checked_at/
    last_raw_description de uno ya visto-no-anunciado-todavía."""
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO processed_incidents(incident_id, first_seen_at, last_checked_at, last_raw_description, last_municipio)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(incident_id) DO UPDATE SET
                last_checked_at = excluded.last_checked_at,
                last_raw_description = excluded.last_raw_description,
                last_municipio = excluded.last_municipio
            WHERE processed_incidents.message_id IS NULL
            """,
            (incident_id, now, now, raw_description, municipio),
        )


def mark_announced(incident_id: int, rule_id: int, message_id: int) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE processed_incidents SET matched_rule_id = ?, message_id = ? WHERE incident_id = ?",
            (rule_id, message_id, incident_id),
        )


def recent_log(limit: int = 200) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT pi.*, r.name AS rule_name, m.text AS message_text, m.sent_at
            FROM processed_incidents pi
            LEFT JOIN alert_rules r ON r.id = pi.matched_rule_id
            LEFT JOIN messages m ON m.id = pi.message_id
            ORDER BY pi.first_seen_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    entries = [dict(r) for r in rows]
    for e in entries:
        e["first_seen_at"] = config.format_timestamp_es(e["first_seen_at"])
        e["sent_at"] = config.format_timestamp_es(e["sent_at"])
    return entries


def purge_older_than(cutoff_iso: str) -> int:
    """Purga incidentes vistos por última vez antes de cutoff_iso. Ver
    models/settings.dedupe_retention_days(). Riesgo aceptado y documentado:
    el feed del 112CV solo lista incidentes activos, así que un id purgado
    hace mucho reaparecería solo en el caso raro de una reapertura tardía."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM processed_incidents WHERE last_checked_at < ?", (cutoff_iso,))
        return cur.rowcount
