"""Catálogo (nunca purgado) de municipios y rutas de taxonomía vistos en el
feed del 112CV. Independiente de processed_incidents (que sí se purga) para
que purgar el dedupe no le borre categorías al desplegable de /rules ni
provoque falsos "categoría nueva" al reaparecer un id purgado."""
from db import db_cursor


def is_known_municipio(municipio: str) -> bool:
    with db_cursor() as cur:
        row = cur.execute("SELECT 1 FROM known_municipios WHERE municipio = ?", (municipio,)).fetchone()
    return row is not None


def is_known_taxonomy_path(raw_description: str) -> bool:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT 1 FROM known_taxonomy_paths WHERE raw_description = ?", (raw_description,)
        ).fetchone()
    return row is not None


def remember_municipio(municipio: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO known_municipios(municipio) VALUES (?) ON CONFLICT(municipio) DO NOTHING",
            (municipio,),
        )


def remember_taxonomy_path(raw_description: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO known_taxonomy_paths(raw_description) VALUES (?) ON CONFLICT(raw_description) DO NOTHING",
            (raw_description,),
        )


def all_municipios() -> list[str]:
    with db_cursor() as cur:
        rows = cur.execute("SELECT municipio FROM known_municipios ORDER BY municipio COLLATE NOCASE").fetchall()
    return [r["municipio"] for r in rows]


def all_category_paths() -> list[list[str]]:
    with db_cursor() as cur:
        rows = cur.execute("SELECT raw_description FROM known_taxonomy_paths").fetchall()
    paths = {tuple(p.strip() for p in r["raw_description"].split(">")) for r in rows}
    return sorted([list(p) for p in paths])
