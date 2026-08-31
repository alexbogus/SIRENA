FROM python:3.12-slim

RUN pip install --no-cache-dir piper-tts flask gunicorn

WORKDIR /app
COPY server.py .

EXPOSE 5100
CMD ["python", "-m", "gunicorn", "--preload", "--bind", "0.0.0.0:5100", "--workers", "1", "--threads", "2", "--timeout", "60", "server:app"]
