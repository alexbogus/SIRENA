FROM python:3.12-slim

RUN pip install --no-cache-dir piper-tts flask gunicorn

# Modelo de voz horneado en la imagen como valor por defecto: el entrypoint
# lo copia a /voices (volumen del host) solo si ese volumen está vacío, así
# el usuario puede seguir actualizando el modelo desde fuera sin rebuild.
RUN python -m piper.download_voices --data-dir /opt/voices-default es_ES-davefx-medium

WORKDIR /app
COPY server.py entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 5100
ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:5100", "--workers", "1", "--threads", "2", "server:app"]
