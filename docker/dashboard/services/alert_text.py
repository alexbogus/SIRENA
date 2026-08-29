"""Árbol de taxonomía 112CV -> frase natural, y construcción del texto final
de alerta. Ver Fase 5 del plan: es un árbol con fallback por nivel, no un
mapa plano de strings exactos, para que una subcategoría nunca vista bajo
un tipo conocido degrade a la frase del nivel superior en vez de a un
fallback genérico feo.

NOTA DE MANTENIMIENTO: este árbol se construyó a partir de un snapshot de
60-64 incidentes reales vistos en agosto de 2026 (el feed del 112CV no
expone un catálogo oficial de categorías). Se espera ampliarlo con el uso;
cualquier categoría que caiga en el fallback genérico queda logueada en
WARNING (ver phrase_for) para poder añadirla aquí.
"""
import config

logger = config.get_logger("alert_text")

TAXONOMY = {
    "Incendio": {
        "_phrase": "un incendio",
        "Vegetación": {
            "_phrase": "un incendio de vegetación",
            "Forestal": "un incendio forestal",
            "Forestal Humo": "un incendio forestal, con presencia de humo",
            "Rural/Montañosa": "un incendio de vegetación en zona rural montañosa",
            "Rural/Montañosa Humo": "un incendio en zona rural montañosa, con presencia de humo",
            "Quema Controlada": "una quema controlada",
        },
    },
    "Accidente": {
        "_phrase": "un accidente",
        "Vehículo": {
            "_phrase": "un accidente de tráfico",
            "Sin Heridos": "un accidente de tráfico sin heridos",
            "Desconoce Heridos": "un accidente de tráfico, se desconoce si hay heridos",
        },
    },
    "Incidencia": {
        "_phrase": "una incidencia",
        "Circulación": {
            "_phrase": "una incidencia de circulación",
            "Red Viaria": "una incidencia en la red viaria",
        },
    },
    "Medioambiente": {
        "_phrase": "una incidencia medioambiental",
        "Animales": {
            "_phrase": "un aviso relacionado con animales",
            "Doméstico": "un aviso sobre un animal doméstico",
            "Marinos": "un aviso sobre fauna marina",
            "Especie Protegida": "un aviso sobre una especie protegida",
        },
        "Contaminación": {
            "_phrase": "un aviso de contaminación",
            "Mar": "un aviso de contaminación marina",
        },
    },
    "Salvamento": {
        "_phrase": "una operación de salvamento",
        "Rescate": {
            "_phrase": "un rescate",
            "Costa": "un rescate en la costa",
        },
    },
}


def _parse_path(description_es: str) -> list[str]:
    return [p.strip() for p in description_es.split(">")]


def phrase_for(description_es: str) -> str:
    path = _parse_path(description_es)
    node = TAXONOMY
    best_phrase = None
    for segment in path:
        if not isinstance(node, dict) or segment not in node:
            break
        child = node[segment]
        if isinstance(child, str):
            best_phrase = child
            node = {}
            break
        best_phrase = child.get("_phrase", best_phrase)
        node = child

    if best_phrase is None:
        logger.warning(
            f"Categoría fuera del árbol de taxonomía, usando fallback genérico: {description_es!r}"
        )
        last_segment = path[-1].lower() if path else description_es.lower()
        return f"una incidencia de tipo {last_segment}"
    return best_phrase


def build_alert_text(description_es: str, municipio: str, street_ref: str | None) -> str:
    phrase = phrase_for(description_es)
    text = f"Atención. {phrase} en la población de {municipio}"
    if street_ref:
        text += f", cerca de {street_ref}"
    return text + "."
