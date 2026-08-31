from db import db_cursor


def list_all() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute("SELECT * FROM zones ORDER BY name COLLATE NOCASE").fetchall()
    return [dict(r) for r in rows]


def list_enabled() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM zones WHERE enabled = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(r) for r in rows]


def get(zone_id: int) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM zones WHERE id = ?", (zone_id,)).fetchone()
    return dict(row) if row else None


def create(name: str) -> int:
    with db_cursor() as cur:
        cur.execute("INSERT INTO zones(name) VALUES (?)", (name,))
        return cur.lastrowid


def update(zone_id: int, name: str) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE zones SET name = ? WHERE id = ?", (name, zone_id))


def set_enabled(zone_id: int, enabled: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE zones SET enabled = ? WHERE id = ?", (1 if enabled else 0, zone_id))


def delete(zone_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM zones WHERE id = ?", (zone_id,))


def speakers_for_zone(zone_id: int) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT s.*, ss.volume_percent
            FROM speakers s
            JOIN speaker_zones sz ON sz.speaker_id = s.id
            LEFT JOIN speaker_status ss ON ss.speaker_id = s.id
            WHERE sz.zone_id = ?
            ORDER BY s.name COLLATE NOCASE
            """,
            (zone_id,),
        ).fetchall()
    return [dict(r) for r in rows]
