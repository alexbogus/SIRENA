"""Descarga en background (vía el scheduler ya usado en el proyecto) de
modelos de voz Piper al volumen compartido con el sidecar piper, con
verificación de integridad (tamaño + MD5) igual que el instalador oficial
`python -m piper.download_voices`. El contenedor piper no participa en
nada de esto -- solo recoge los ficheros nuevos en su próxima carga
perezosa, ya lazy por diseño (ver server.py)."""
import hashlib

import requests

import config
import models.voices as voices_model
import services.voices_catalog as voices_catalog
from scheduler import scheduler

logger = config.get_logger("voice_downloader")

_CHUNK_SIZE = 1024 * 1024


def enqueue_download(voice_key: str) -> bool:
    """Lanza la descarga en background si no hay ya una en curso para esta
    voz. Devuelve False si el job no se lanzó (voz desconocida o ya
    descargándose)."""
    if voices_catalog.get(voice_key) is None:
        return False
    running = voices_model.get_download(voice_key)
    if running and running["status"] == "running":
        return False

    voices_model.start_download_row(voice_key)
    scheduler.add_job(
        download_voice, args=[voice_key],
        id=f"voice_download_{voice_key}", replace_existing=True,
        max_instances=1, coalesce=True,
    )
    return True


def download_voice(voice_key: str) -> None:
    voice = voices_catalog.get(voice_key)
    if voice is None:
        voices_model.set_download_status(voice_key, "error", "Voz no encontrada en el catálogo")
        return

    onnx_dest = voices_model.VOICES_DIR / voice["filename"]
    json_dest = voices_model.VOICES_DIR / voice["json_filename"]

    try:
        voices_model.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        _download_and_verify(voice["url_onnx"], onnx_dest, voice["size_bytes_onnx"], voice["md5_onnx"])
        try:
            _download_and_verify(
                voice["url_onnx_json"], json_dest, voice["size_bytes_onnx_json"], voice["md5_onnx_json"]
            )
        except Exception:
            # Sin sidecar no hay par válido -- no dejar un .onnx huérfano
            # que server.py podría intentar cargar sin metadatos.
            onnx_dest.unlink(missing_ok=True)
            raise
    except Exception as exc:
        logger.exception(f"Fallo descargando voz {voice_key}")
        voices_model.set_download_status(voice_key, "error", str(exc))
        return

    voices_model.set_download_status(voice_key, "done")
    logger.info(f"Voz descargada y verificada: {voice_key}")


def _download_and_verify(url: str, dest_path, expected_size: int, expected_md5: str) -> None:
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    md5 = hashlib.md5()
    size = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    f.write(chunk)
                    md5.update(chunk)
                    size += len(chunk)

        if size != expected_size or md5.hexdigest() != expected_md5:
            raise ValueError(
                f"Verificación de integridad fallida para {dest_path.name} "
                f"(tamaño {size}/{expected_size}, md5 {md5.hexdigest()}/{expected_md5})"
            )
        tmp_path.replace(dest_path)
    finally:
        tmp_path.unlink(missing_ok=True)
