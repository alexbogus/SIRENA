"""Copias de seguridad de la base de datos SQLite. Usa la API de backup
integrada en el módulo sqlite3 (Connection.backup), no un `cp` a pelo -- es
la vía segura para copiar una base de datos que puede estar abierta/en uso
en ese momento (por el propio proceso, vía scheduler), evita copias a medio
escribir. docker/update.sh usa el mismo mecanismo pero desde el CLI
`sqlite3` (no tiene el intérprete de la app disponible), por eso el nombre
de archivo (dashboard_AAAAMMDD_HHMMSS.db) y la carpeta (config.BACKUP_DIR)
están alineados entre ambos: cualquiera de los dos lee las copias del otro."""
import datetime
import shutil
import sqlite3
import time
from pathlib import Path

import config

_FILENAME_GLOB = "dashboard_*.db"
_FILENAME_FMT = "dashboard_%Y%m%d_%H%M%S.db"
_MIN_HEADER = b"SQLite format 3\x00"
# Tablas presentes desde el primer schema.sql -- si faltan, casi seguro no es
# un dashboard.db de SIRENA (o es de un esquema demasiado viejo/roto).
_REQUIRED_TABLES = {"settings", "speakers", "alert_rules", "tones"}


class InvalidBackupError(Exception):
    """El archivo dado no es una base de datos de SIRENA restaurable."""


def create_backup() -> Path:
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.BACKUP_DIR / time.strftime(_FILENAME_FMT)
    src_conn = sqlite3.connect(config.DB_PATH)
    try:
        dest_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return dest


def list_backups() -> list[dict]:
    if not config.BACKUP_DIR.exists():
        return []
    rows = []
    for path in sorted(config.BACKUP_DIR.glob(_FILENAME_GLOB), reverse=True):
        stat = path.stat()
        rows.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y - %H:%M:%S"),
        })
    return rows


def prune_old_backups(retention_days: int | None = None) -> int:
    retention_days = config.BACKUP_RETENTION_DAYS if retention_days is None else retention_days
    if not config.BACKUP_DIR.exists():
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for path in config.BACKUP_DIR.glob(_FILENAME_GLOB):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


def validate_backup_file(path: Path) -> None:
    with open(path, "rb") as f:
        header = f.read(len(_MIN_HEADER))
    if header != _MIN_HEADER:
        raise InvalidBackupError("El archivo no es una base de datos SQLite válida.")

    conn = sqlite3.connect(path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.DatabaseError as exc:
        raise InvalidBackupError(f"No se pudo leer la base de datos: {exc}") from exc
    finally:
        conn.close()

    missing = _REQUIRED_TABLES - tables
    if missing:
        raise InvalidBackupError(f"Faltan tablas esperadas de SIRENA: {', '.join(sorted(missing))}.")


def restore_from(path: Path) -> None:
    """Restaura `path` como la base de datos activa. Valida antes que sea
    una BD de SIRENA (ver validate_backup_file) y se hace un backup de
    seguridad del estado ACTUAL primero -- así el propio restore es
    reversible. No reinicia el proceso: quien llame (routes/settings.py)
    decide cuándo forzarlo, para poder responder antes al navegador."""
    validate_backup_file(path)
    create_backup()
    shutil.copyfile(path, config.DB_PATH)
