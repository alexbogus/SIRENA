"""Configuración por variables de entorno y arranque del logging estructurado."""
import json
import logging
import logging.handlers
import os
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
LOGS_DIR = Path(os.environ.get("LOGS_DIR", BASE_DIR / "logs"))
DB_PATH = Path(os.environ.get("DB_PATH", DATA_DIR / "dashboard.db"))

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()

PIPER_URL = os.environ.get("PIPER_URL", "http://127.0.0.1:5100/synthesize")
PIPER_VOICES_DIR = Path(os.environ.get("PIPER_VOICES_DIR", "/voices"))
CV112_FEED_URL = os.environ.get(
    "CV112_FEED_URL",
    "https://wpr.112cv.gva.es/external/api/storage/descargar/geojson/incidentes/incidente.geojson",
)

DEFAULT_STATUS_POLL_INTERVAL_S = int(os.environ.get("STATUS_POLL_INTERVAL_S", "10"))
DEFAULT_CV112_POLL_INTERVAL_S = int(os.environ.get("CV112_POLL_INTERVAL_S", "45"))
DELIVERY_CONFIRMATION_DELAY_S = int(os.environ.get("DELIVERY_CONFIRMATION_DELAY_S", "5"))
DELIVERY_CONFIRMATION_MARGIN_S = int(os.environ.get("DELIVERY_CONFIRMATION_MARGIN_S", "5"))
SYSTEM_HEALTH_FAILURE_THRESHOLD = int(os.environ.get("SYSTEM_HEALTH_FAILURE_THRESHOLD", "5"))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:8]


def now_sql() -> str:
    """Timestamp en hora local del servidor, formato 'YYYY-MM-DD HH:MM:SS'
    (comparable con SQLite datetime('now'), pero en hora local en vez de
    UTC -- consistente con el resto de timestamps de la app, ej. los del
    firmware, que también son hora local)."""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_timestamp_es(sql_timestamp: str) -> str:
    """'YYYY-MM-DD HH:MM:SS' -> 'DD/MM/YYYY - HH:MM:ss', mismo formato que
    usa el firmware en /status."""
    import datetime
    try:
        dt = datetime.datetime.strptime(sql_timestamp, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return sql_timestamp
    return dt.strftime("%d/%m/%Y - %H:%M:%S")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    if any(isinstance(h, logging.handlers.TimedRotatingFileHandler) for h in root.handlers):
        return  # ya configurado (recarga del reloader de Flask en debug, etc.)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOGS_DIR / "dashboard.log", when="midnight", backupCount=LOG_RETENTION_DAYS, encoding="utf-8"
    )
    file_handler.setFormatter(_JsonFormatter())
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_JsonFormatter())
    root.addHandler(console_handler)


class _ComponentLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter que añade 'component' pero deja pasar 'correlation_id'
    por llamada (logger.info(msg, extra={'correlation_id': cid}))."""

    def process(self, msg, kwargs):
        extra = dict(self.extra)
        extra.update(kwargs.get("extra") or {})
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(component: str) -> logging.LoggerAdapter:
    """Logger que añade automáticamente el campo 'component' a cada línea."""
    return _ComponentLoggerAdapter(logging.getLogger(component), {"component": component})
