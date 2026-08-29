from db import db_cursor


def list_all() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT s.*, ss.firmware_version, ss.rssi_dbm, ss.state, ss.volume_percent,
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


def create(name: str, ip: str, port: int, zone_ids: list[int]) -> int:
    with db_cursor() as cur:
        cur.execute("INSERT INTO speakers(name, ip, port) VALUES (?, ?, ?)", (name, ip, port))
        speaker_id = cur.lastrowid
        _set_zones(cur, speaker_id, zone_ids)
    return speaker_id


def update(speaker_id: int, name: str, ip: str, port: int, zone_ids: list[int]) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE speakers SET name = ?, ip = ?, port = ? WHERE id = ?",
            (name, ip, port, speaker_id),
        )
        _set_zones(cur, speaker_id, zone_ids)


def delete(speaker_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM speakers WHERE id = ?", (speaker_id,))


def _set_zones(cur, speaker_id: int, zone_ids: list[int]) -> None:
    cur.execute("DELETE FROM speaker_zones WHERE speaker_id = ?", (speaker_id,))
    cur.executemany(
        "INSERT INTO speaker_zones(speaker_id, zone_id) VALUES (?, ?)",
        [(speaker_id, zid) for zid in zone_ids],
    )


def resolve_targets(zone_ids: list[int] | None, all_speakers: bool) -> list[dict]:
    """Resuelve una selección de zonas (o el target especial 'todos') a la
    lista de altavoces únicos correspondiente."""
    if all_speakers or not zone_ids:
        if all_speakers:
            with db_cursor() as cur:
                rows = cur.execute("SELECT * FROM speakers").fetchall()
            return [dict(r) for r in rows]
        return []
    with db_cursor() as cur:
        placeholders = ",".join("?" for _ in zone_ids)
        rows = cur.execute(
            f"""
            SELECT DISTINCT s.* FROM speakers s
            JOIN speaker_zones sz ON sz.speaker_id = s.id
            WHERE sz.zone_id IN ({placeholders})
            """,
            zone_ids,
        ).fetchall()
    return [dict(r) for r in rows]


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
                    speaker_id, firmware_version, rssi_dbm, state, volume_percent,
                    last_message_at, last_healthcheck_at, uptime_seconds, last_poll_ok, last_poll_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(speaker_id) DO UPDATE SET
                    firmware_version = excluded.firmware_version,
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
