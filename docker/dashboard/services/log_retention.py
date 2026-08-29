"""Job diario de purga: aplica los períodos de retención configurables en
/settings a los logs retenidos en BD (mensajes, errores de altavoz,
auditoría) y al estado de dedupe del 112CV (retención propia, ver
models/settings.dedupe_retention_days)."""
import datetime

import config
import models.audit as audit_model
import models.incidents as incidents_model
import models.messages as messages_model
import models.settings as settings_model
import models.speaker_errors as speaker_errors_model

logger = config.get_logger("log_retention")


def _cutoff(days: int) -> str:
    return (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def run_once() -> None:
    log_cutoff = _cutoff(settings_model.db_log_retention_days())
    dedupe_cutoff = _cutoff(settings_model.dedupe_retention_days())

    deleted_messages = messages_model.purge_older_than(log_cutoff)
    deleted_errors = speaker_errors_model.purge_older_than(log_cutoff)
    deleted_audit = audit_model.purge_older_than(log_cutoff)
    deleted_incidents = incidents_model.purge_older_than(dedupe_cutoff)

    if deleted_messages or deleted_errors or deleted_audit or deleted_incidents:
        logger.info(
            f"Purga de retención: {deleted_messages} mensajes, {deleted_errors} errores de altavoz, "
            f"{deleted_audit} entradas de auditoría (cutoff {log_cutoff}); "
            f"{deleted_incidents} incidentes de dedupe (cutoff {dedupe_cutoff})"
        )
