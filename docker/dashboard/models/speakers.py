import requests

from db import db_cursor


def list_all() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT s.*, ss.firmware_version, ss.mac, ss.rssi_dbm, ss.state, ss.volume_percent,
                   ss.last_message_at, ss.last_healthcheck_at, ss.uptime_seconds,
                   ss.last_poll_ok, ss.last_poll_at
            FROM speakers s
            LEFT JOIN speaker_status ss ON ss.speaker_id = s.id
            ORDER BY s.name COLLATE NOCASE
            """
        ).fetchall()
    speakers = [dict(r) for r in rows]
    for sp in speakers:
        sp["zones"] = zones_for_speaker(sp["id"])
    return speakers


def get(speaker_id: int) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM speakers WHERE id = ?", (speaker_id,)).fetchone()
    return dict(row) if row else None


def zones_for_speaker(speaker_id: int) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT z.* FROM zones z
            JOIN speaker_zones sz ON sz.zone_id = z.id
            WHERE sz.speaker_id = ?
            ORDER BY z.name COLLATE NOCASE
            """,
            (speaker_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create(name: str, ip: str, port: int, zone_ids: list[int], description: str | None = None) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO speakers(name, ip, port, description) VALUES (?, ?, ?, ?)",
            (name, ip, port, description),
        )
        speaker_id = cur.lastrowid
        _set_zones(cur, speaker_id, zone_ids)
    return speaker_id


def update(
    speaker_id: int, name: str, ip: str, port: int, zone_ids: list[int], description: str | None = None
) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE speakers SET name = ?, ip = ?, port = ?, description = ? WHERE id = ?",
            (name, ip, port, description, speaker_id),
        )
        _set_zones(cur, speaker_id, zone_ids)


def set_enabled(speaker_id: int, enabled: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE speakers SET enabled = ? WHERE id = ?", (1 if enabled else 0, speaker_id))


def delete(speaker_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM speakers WHERE id = ?", (speaker_id,))


def _set_zones(cur, speaker_id: int, zone_ids: list[int]) -> None:
    cur.execute("DELETE FROM speaker_zones WHERE speaker_id = ?", (speaker_id,))
    cur.executemany(
        "INSERT INTO speaker_zones(speaker_id, zone_id) VALUES (?, ?)",
        [(speaker_id, zid) for zid in zone_ids],
    )


def resolve_targets(
    zone_ids: list[int] | None, all_speakers: bool, speaker_ids: list[int] | None = None
) -> list[dict]:
    """Resuelve una selección de zonas, altavoces individuales, o el target
    especial 'todos', a la lista de altavoces únicos correspondiente.
    Prioridad: all_speakers > speaker_ids > zone_ids."""
    if all_speakers:
        with db_cursor() as cur:
            rows = cur.execute("SELECT * FROM speakers WHERE enabled = 1").fetchall()
        return [dict(r) for r in rows]
    if speaker_ids:
        with db_cursor() as cur:
            placeholders = ",".join("?" for _ in speaker_ids)
            rows = cur.execute(
                f"SELECT * FROM speakers WHERE enabled = 1 AND id IN ({placeholders})",
                speaker_ids,
            ).fetchall()
        return [dict(r) for r in rows]
    if not zone_ids:
        return []
    with db_cursor() as cur:
        placeholders = ",".join("?" for _ in zone_ids)
        rows = cur.execute(
            f"""
            SELECT DISTINCT s.* FROM speakers s
            JOIN speaker_zones sz ON sz.speaker_id = s.id
            WHERE s.enabled = 1 AND sz.zone_id IN ({placeholders})
            """,
            zone_ids,
        ).fetchall()
    return [dict(r) for r in rows]


def push_volume(speaker: dict, volume_percent: int) -> bool:
    """Envía el volumen al firmware del altavoz y lo persiste si responde. Devuelve éxito."""
    try:
        resp = requests.post(f"http://{speaker['ip']}/volume", json={"volume_percent": volume_percent}, timeout=3)
        resp.raise_for_status()
    except Exception:
        return False
    set_volume(speaker["id"], volume_percent)
    return True


def set_volume(speaker_id: int, volume_percent: int) -> None:
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO speaker_status(speaker_id, volume_percent) VALUES (?, ?)
            ON CONFLICT(speaker_id) DO UPDATE SET volume_percent = excluded.volume_percent
            """,
            (speaker_id, volume_percent),
        )


def upsert_status(speaker_id: int, status: dict, poll_ok: bool, poll_at: str) -> None:
    with db_cursor() as cur:
        if poll_ok:
            cur.execute(
                """
                INSERT INTO speaker_status(
                    speaker_id, firmware_version, mac, rssi_dbm, state, volume_percent,
                    last_message_at, last_healthcheck_at, uptime_seconds, last_poll_ok, last_poll_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(speaker_id) DO UPDATE SET
                    firmware_version = excluded.firmware_version,
                    mac = excluded.mac,
                    rssi_dbm = excluded.rssi_dbm,
                    state = excluded.state,
                    volume_percent = excluded.volume_percent,
                    last_message_at = excluded.last_message_at,
                    last_healthcheck_at = excluded.last_healthcheck_at,
                    uptime_seconds = excluded.uptime_seconds,
                    last_poll_ok = 1,
                    last_poll_at = excluded.last_poll_at
                """,
                (
                    speaker_id,
                    status.get("firmware_version"),
                    status.get("mac"),
                    status.get("rssi_dbm"),
                    status.get("state"),
                    status.get("volume_percent"),
                    status.get("last_message_at"),
                    status.get("last_healthcheck_at"),
                    status.get("uptime_seconds"),
                    poll_at,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO speaker_status(speaker_id, last_poll_ok, last_poll_at)
                VALUES (?, 0, ?)
                ON CONFLICT(speaker_id) DO UPDATE SET last_poll_ok = 0, last_poll_at = excluded.last_poll_at
                """,
                (speaker_id, poll_at),
            )
