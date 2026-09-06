"""Tokens de API para integraciones externas (n8n, etc.). Ver
services/api_tokens.py para la emisión/verificación del token en sí --
este módulo es solo el CRUD sobre la tabla, mismo estilo que models/zones.py."""
import json

import config
from db import db_cursor


def create(token_id: str, secret_hash: str, name: str, zone_ids: list[int] | None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO api_tokens(id, secret_hash, name, zone_ids, created_at) VALUES (?, ?, ?, ?, ?)",
            (token_id, secret_hash, name, json.dumps(zone_ids) if zone_ids else None, config.now_sql()),
        )


def _parse(row) -> dict:
    d = dict(row)
    d["zone_ids"] = json.loads(d["zone_ids"]) if d["zone_ids"] else None
    return d


def get(token_id: str) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM api_tokens WHERE id = ?", (token_id,)).fetchone()
    return _parse(row) if row else None


def list_all() -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute("SELECT * FROM api_tokens ORDER BY created_at DESC").fetchall()
    return [_parse(r) for r in rows]


def set_revoked(token_id: str, revoked: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE api_tokens SET revoked = ? WHERE id = ?", (1 if revoked else 0, token_id))


def delete(token_id: str) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM api_tokens WHERE id = ?", (token_id,))


def touch_last_used(token_id: str) -> None:
    # Timestamp explícito en hora local (config.now_sql()), no el
    # datetime('now') de SQLite -- ese es UTC y desentonaría con el resto
    # de fechas que se muestran en la GUI (todas en hora local del
    # servidor, ver config.now_sql()).
    with db_cursor() as cur:
        cur.execute(
            "UPDATE api_tokens SET last_used_at = ? WHERE id = ?", (config.now_sql(), token_id)
        )
