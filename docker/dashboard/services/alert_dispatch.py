"""Pipeline común de envío de un aviso a un conjunto de altavoces: texto ->
WAV (TTS) -> trazabilidad en BD -> envío UDP -> confirmación de entrega.
Extraído de routes/manual_send.py para que también lo use routes/api_v1.py
(DRY) sin duplicar la lógica de envío ni el registro de errores.

dispatch() es el camino "de siempre" (interrumpe lo que esté sonando,
usado por el envío manual y, en el futuro, por cualquier fuente que deba
comportarse igual). dispatch_with_queue() es exclusivo de la API: si un
altavoz destino ya está reproduciendo algo, el mensaje se encola para él
en vez de interrumpirlo -- ver services/queue_dispatcher.py."""
import datetime
import shutil
from pathlib import Path

import config
import models.message_queue as message_queue_model
import models.messages as messages_model
import models.speaker_errors as speaker_errors_model
import models.settings as settings_model
from services.delivery_confirmation import schedule_confirmation_for, schedule_confirmations
from services.sender import send_to_many
from services.status_poller import fetch_status
from services.tts import build_alert_wav

logger = config.get_logger("alert_dispatch")

QUEUE_AUDIO_DIR = config.DATA_DIR / "queue_audio"


def dispatch(scheduler, text: str, targets: list[dict], target_label: str, tone_id: int | None = None,
             source: str = "manual", api_token_id: str | None = None,
             api_token_name: str | None = None) -> tuple[int, dict[int, bool]]:
    """Sintetiza `text` y lo envía de inmediato a todos los `targets`
    (interrumpiendo lo que estuvieran reproduciendo, comportamiento de
    siempre). Devuelve (message_id, {speaker_id: send_ok})."""
    wav_path = build_alert_wav(text, tone_id=tone_id)
    try:
        target_speaker_ids = [t["id"] for t in targets]
        message_id = messages_model.create(
            source=source, text=text, speaker_ids=target_speaker_ids, target_label=target_label,
            api_token_id=api_token_id, api_token_name=api_token_name,
        )
        sent_at = datetime.datetime.now().isoformat(timespec="seconds")

        send_results = send_to_many([(t["id"], t["ip"], t["port"]) for t in targets], wav_path)
        for speaker_id, ok in send_results.items():
            messages_model.set_send_result(message_id, speaker_id, ok)
            if not ok:
                speaker_name = next((t["name"] for t in targets if t["id"] == speaker_id), speaker_id)
                speaker_errors_model.record(speaker_id, f"Fallo al enviar mensaje ({source}) a {speaker_name!r}")
    finally:
        Path(wav_path).unlink(missing_ok=True)

    schedule_confirmations(scheduler, message_id, sent_at)
    return message_id, send_results


def dispatch_with_queue(scheduler, text: str, targets: list[dict], target_label: str,
                         tone_id: int | None = None, api_token_id: str | None = None,
                         api_token_name: str | None = None) -> dict:
    """Como dispatch(), pero para cada altavoz que ya esté reproduciendo
    algo (según su /status en el momento del envío) el mensaje se encola en
    vez de interrumpirlo -- ver services/queue_dispatcher.py, que lo
    entregará en cuanto el altavoz quede libre (o lo descarta si expira
    settings.api_queue_ttl_s). Devuelve {message_id, dispatched, queued}."""
    wav_path = build_alert_wav(text, tone_id=tone_id)
    target_speaker_ids = [t["id"] for t in targets]
    message_id = messages_model.create(
        source="api", text=text, speaker_ids=target_speaker_ids, target_label=target_label,
        api_token_id=api_token_id, api_token_name=api_token_name,
    )
    sent_at = datetime.datetime.now().isoformat(timespec="seconds")

    busy, idle = [], []
    for t in targets:
        status = fetch_status(t["ip"])
        (busy if status and status.get("state") == "streaming" else idle).append(t)

    dispatched_ids: list[int] = []
    if idle:
        send_results = send_to_many([(t["id"], t["ip"], t["port"]) for t in idle], wav_path)
        for speaker_id, ok in send_results.items():
            messages_model.set_send_result(message_id, speaker_id, ok)
            if not ok:
                speaker_name = next((t["name"] for t in idle if t["id"] == speaker_id), speaker_id)
                speaker_errors_model.record(speaker_id, f"Fallo al enviar mensaje (api) a {speaker_name!r}")
        dispatched_ids = list(send_results.keys())

    queued_ids: list[int] = []
    if busy:
        QUEUE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        queued_wav = QUEUE_AUDIO_DIR / f"msg{message_id}_{Path(wav_path).name}"
        shutil.copy2(wav_path, queued_wav)
        ttl = settings_model.api_queue_ttl_s()
        expires_at = (datetime.datetime.now() + datetime.timedelta(seconds=ttl)).strftime("%Y-%m-%d %H:%M:%S")
        for t in busy:
            message_queue_model.enqueue(message_id, t["id"], str(queued_wav), expires_at)
            logger.info(f"Mensaje {message_id} encolado para {t['name']!r} (ocupado), expira en {ttl}s")
        queued_ids = [t["id"] for t in busy]

    Path(wav_path).unlink(missing_ok=True)
    if dispatched_ids:
        # Solo los targets despachados AHORA -- los que se quedan en cola
        # (`busy`) se confirmarán con su propio sent_at cuando
        # queue_dispatcher los entregue de verdad, no con este.
        for target in messages_model.targets_with_speaker(message_id):
            if target["speaker_id"] in dispatched_ids:
                schedule_confirmation_for(scheduler, target["id"], message_id,
                                           target["speaker_id"], target["speaker_ip"], sent_at)
    return {"message_id": message_id, "dispatched": dispatched_ids, "queued": queued_ids}


def resolve_names_to_ids(names: list[str], catalog: list[dict]) -> tuple[list[int], list[str]]:
    """Traduce una lista de nombres (case-insensitive) a ids usando un
    catálogo ya cargado (zones_model.list_all(), speakers_model.list_all(),
    tones_model.list_enabled()...). Devuelve (ids, nombres_no_encontrados)."""
    by_name = {c["name"].strip().lower(): c["id"] for c in catalog}
    ids, missing = [], []
    for name in names:
        found = by_name.get(name.strip().lower())
        if found is None:
            missing.append(name)
        else:
            ids.append(found)
    return ids, missing
