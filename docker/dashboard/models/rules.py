import json

from db import db_cursor


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
           target_zone_id: int | None, enabled: bool) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO alert_rules(name, municipios, categorias, target_zone_id, enabled) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, json.dumps(municipios), json.dumps(categorias), target_zone_id, 1 if enabled else 0),
        )
        return cur.lastrowid


def update(rule_id: int, name: str, municipios: list[str], categorias: list[list[str]],
           target_zone_id: int | None, enabled: bool) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE alert_rules SET name = ?, municipios = ?, categorias = ?, "
            "target_zone_id = ?, enabled = ? WHERE id = ?",
            (name, json.dumps(municipios), json.dumps(categorias), target_zone_id,
             1 if enabled else 0, rule_id),
        )


def delete(rule_id: int) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))


def matches(rule: dict, municipio: str, category_path: list[str]) -> bool:
    if rule["municipios"]:
        if not municipio or municipio.strip().lower() not in [m.strip().lower() for m in rule["municipios"]]:
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
