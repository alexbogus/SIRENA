"""Lee CHANGELOG.md (montado en config.CHANGELOG_PATH, ver docker-compose.yml)
para mostrar la versión actual en el sidebar y su contenido renderizado en el
modal de novedades. La versión "actual" es simplemente el primer encabezado
`## [X.Y.Z]` del archivo -- publicar una versión nueva es tan sencillo como
añadir una sección al principio de CHANGELOG.md, sin tocar código."""
import re

import markdown

import config

_VERSION_RE = re.compile(r"^## \[(?P<version>[^\]]+)\]", re.MULTILINE)
_UNKNOWN_VERSION = "?"


def current_version() -> str:
    text = _read_text()
    if text is None:
        return _UNKNOWN_VERSION
    match = _VERSION_RE.search(text)
    return match.group("version") if match else _UNKNOWN_VERSION


def render_html() -> str:
    text = _read_text()
    if text is None:
        return "<p>CHANGELOG.md no disponible.</p>"
    return markdown.markdown(text)


def _read_text() -> str | None:
    if not config.CHANGELOG_PATH.exists():
        return None
    return config.CHANGELOG_PATH.read_text(encoding="utf-8")
