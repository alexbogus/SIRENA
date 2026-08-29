FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus0 ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY _protocol_sender.py /app/_protocol_sender.py
COPY dashboard/ /app/

RUN mkdir -p /app/data /app/logs

EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -fs http://127.0.0.1:8080/healthz || exit 1
# Un solo worker: el scheduler de APScheduler vive en memoria del proceso,
# con varios workers cada uno lanzaría su propio scheduler y duplicaría
# envíos/polls. --threads da la concurrencia necesaria para las peticiones HTTP.
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "app:app"]
