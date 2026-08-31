import json

from db import db_cursor
from models.taxonomy import normalized_forms


def list_all(enabled_only: bool = False) -> list[dict]:
    query = "SELECT * FROM alert_rules"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY id"
    with db_cursor() as cur:
        rows = cur.execute(query).fetchall()
    rules = []
    for r in rows:
        d = dict(r)
        d["municipios"] = json.loads(d["municipios"]) if d["municipios"] else []
        d["categorias"] = json.loads(d["categorias"]) if d["categorias"] else []
        rules.append(d)
    return rules


def get(rule_id: int) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM alert_rules WHERE id = ?", (rule_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["municipios"] = json.loads(d["municipios"]) if d["municipios"] else []
    d["categorias"] = json.loads(d["categorias"]) if d["categorias"] else []
    return d


def create(name: str, municipios: list[str], categorias: list[list[str]],
           target_zone_id: int | None, tone_id: int | None, enabled: bool) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO alert_rules(name, municipios, categorias, target_zone_id, tone_id, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, json.dumps(municipios), json.dumps(categorias), target_zone_id, tone_id,
             1 if enabled else 0),
        )
        return cur.lastrowid


def update(rule_id: int, name: str, municipios: list[str], categorias: list[list[str]],
           target_zone_id: int | None, tone_id: int | None, enabled: bool) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE alert_rules SET name = ?, municipios = ?, categorias = ?, "
            "target_zone_id = ?, tone_id = ?, enabled = ? WHERE id = ?",
            (name, json.dumps(municipios), json.dumps(categorias), target_zone_id, tone_id,
             1 if enabled else 0, rule_id),
        )


def set_enabled(rule_id: int, enabled: bool) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE alert_rules SET enabled = ? WHERE id = ?", (1 if enabled else 0, rule_id))


def delete(rule_id: int) -> None:
    with db_cursor() as cur:
        # messages.rule_id y processed_incidents.matched_rule_id son
        # REFERENCES alert_rules(id) sin ON DELETE (SQLite no permite
        # cambiar eso vía ALTER TABLE), así que borrar una regla ya usada
        # violaba la FK -- se desvincula el historial en vez de bloquear el
        # borrado, igual que target_label ya congela el destino de un
        # mensaje aunque la zona deje de existir.
        cur.execute("UPDATE messages SET rule_id = NULL WHERE rule_id = ?", (rule_id,))
        cur.execute("UPDATE processed_incidents SET matched_rule_id = NULL WHERE matched_rule_id = ?", (rule_id,))
        cur.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))


def matches(rule: dict, municipio: str, category_path: list[str]) -> bool:
    if rule["municipios"]:
        if not municipio:
            return False
        incident_forms = normalized_forms(municipio)
        rule_forms = {f for m in rule["municipios"] for f in normalized_forms(m)}
        if not (incident_forms & rule_forms):
            return False
    if rule["categorias"]:
        matched_any = False
        for allowed_path in rule["categorias"]:
            if category_path[:len(allowed_path)] == allowed_path:
                matched_any = True
                break
        if not matched_any:
            return False
    return True


def find_first_match(municipio: str, category_path: list[str]) -> dict | None:
    for rule in list_all(enabled_only=True):
        if matches(rule, municipio, category_path):
            return rule
    return None
