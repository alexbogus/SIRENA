from db import db_cursor


def list_all() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute("SELECT * FROM tones ORDER BY name COLLATE NOCASE").fetchall()
    return [dict(r) for r in rows]


def list_enabled() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM tones WHERE enabled = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(r) for r in rows]


def get(tone_id: int) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM tones WHERE id = ?", (tone_id,)).fetchone()
    return dict(row) if row else None


def get_default() -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM tones WHERE is_default = 1").fetchone()
    return dict(row) if row else None


def create(name: str, filename: str) -> int:
    with db_cursor() as cur:
        cur.execute("INSERT INTO tones(name, filename) VALUES (?, ?)", (name, filename))
        return cur.lastrowid


def set_enabled(tone_id: int, enabled: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE tones SET enabled = ? WHERE id = ?", (1 if enabled else 0, tone_id))


def set_default(tone_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE tones SET is_default = 0")
        cur.execute("UPDATE tones SET is_default = 1 WHERE id = ?", (tone_id,))


def delete(tone_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM tones WHERE id = ?", (tone_id,))
