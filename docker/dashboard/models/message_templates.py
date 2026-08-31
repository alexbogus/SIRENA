from db import db_cursor


def list_all() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM message_templates ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get(template_id: int) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT * FROM message_templates WHERE id = ?", (template_id,)
        ).fetchone()
    return dict(row) if row else None


def create(name: str, text: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO message_templates(name, text) VALUES (?, ?)", (name, text)
        )
        return cur.lastrowid


def delete(template_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
