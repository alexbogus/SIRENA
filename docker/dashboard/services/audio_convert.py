import subprocess

TONE_SAMPLE_RATE = 16000


def normalize_to_tone_wav(src_path: str, dst_path: str) -> None:
    """Convierte cualquier audio que ffmpeg sepa decodificar (wav, mp3, ogg, m4a...)
    al formato exigido por el pipeline de envío: 16kHz mono PCM 16-bit.
    Lanza subprocess.CalledProcessError si el archivo no se puede decodificar."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src_path,
         "-ar", str(TONE_SAMPLE_RATE), "-ac", "1", "-sample_fmt", "s16", dst_path],
        check=True,
    )
