"""Emisión y verificación de tokens de API opacos (formato
"sirena_<id>_<secret>", análogo a un Personal Access Token de GitHub). Solo
se guarda en BD el hash bcrypt del secreto -- el valor en claro se devuelve
una única vez, al crearlo (ver routes/settings.py)."""
import secrets

import bcrypt

import config
import models.api_tokens as api_tokens_model

logger = config.get_logger("api_tokens")

_PREFIX = "sirena"


def issue(name: str, zone_ids: list[int] | None) -> str:
    """Crea un token nuevo y devuelve el valor completo en claro. No se
    conserva en ningún sitio a partir de este punto -- solo su hash."""
    token_id = secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    secret_hash = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    api_tokens_model.create(token_id, secret_hash, name, zone_ids)
    return f"{_PREFIX}_{token_id}_{secret}"


def verify(raw_token: str) -> dict | None:
    """Valida un token recibido en la cabecera Authorization. Devuelve
    {id, name, zone_ids} si es válido y no está revocado, None en cualquier
    otro caso (formato inválido, id desconocido, secreto incorrecto,
    revocado)."""
    parts = raw_token.split("_", 2)
    if len(parts) != 3 or parts[0] != _PREFIX:
        return None
    _, token_id, secret = parts

    row = api_tokens_model.get(token_id)
    if row is None or row["revoked"]:
        return None
    if not bcrypt.checkpw(secret.encode("utf-8"), row["secret_hash"].encode("utf-8")):
        return None

    api_tokens_model.touch_last_used(token_id)
    return {"id": row["id"], "name": row["name"], "zone_ids": row["zone_ids"]}
