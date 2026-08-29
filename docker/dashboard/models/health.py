from db import db_cursor


def report_ok(component: str, now: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO system_health(component, last_ok_at, consecutive_failures)
            VALUES (?, ?, 0)
            ON CONFLICT(component) DO UPDATE SET last_ok_at = excluded.last_ok_at, consecutive_failures = 0
            """,
            (component, now),
        )


def report_failure(component: str, now: str, message: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO system_health(component, last_error_at, last_error_message, consecutive_failures)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(component) DO UPDATE SET
                last_error_at = excluded.last_error_at,
                last_error_message = excluded.last_error_message,
                consecutive_failures = system_health.consecutive_failures + 1
            """,
            (component, now, message),
        )
        row = cur.execute(
            "SELECT consecutive_failures FROM system_health WHERE component = ?", (component,)
        ).fetchone()
    return row["consecutive_failures"] if row else 1


def get_all() -> dict[str, dict]:
    with db_cursor() as cur:
        rows = cur.execute("SELECT * FROM system_health").fetchall()
    return {r["component"]: dict(r) for r in rows}
