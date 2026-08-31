import sys
from pathlib import Path

# _protocol_sender.py vive en docker/, un nivel por encima de dashboard/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask

import config
import db
import models.settings as settings_model
import models.voices as voices_model
from scheduler import scheduler
from services.cv112_poller import poll_once as cv112_poll_once
from services.log_retention import run_once as log_retention_run_once
from services.status_poller import poll_once as status_poll_once

config.configure_logging()
logger = config.get_logger("app")


def create_app() -> Flask:
    app = Flask(__name__)
    db.init_db()
    voices_model.mark_interrupted_downloads()
    app.secret_key = config.SECRET_KEY or _fallback_secret_key()

    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.speakers import bp as speakers_bp
    from routes.zones import bp as zones_bp
    from routes.manual_send import bp as manual_send_bp
    from routes.rules import bp as rules_bp
    from routes.settings import bp as settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(speakers_bp)
    app.register_blueprint(zones_bp)
    app.register_blueprint(manual_send_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(settings_bp)

    @app.get("/healthz")
    def healthz():
        with db.db_cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok"}, 200

    _start_scheduler()
    return app


def _fallback_secret_key() -> str:
    # Persistimos una clave generada en settings para que las sesiones
    # sobrevivan a reinicios del contenedor si no se pasó SECRET_KEY por env.
    key = settings_model.get("flask_secret_key")
    if not key:
        import secrets
        key = secrets.token_hex(32)
        settings_model.set("flask_secret_key", key)
    return key


def _start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        status_poll_once, "interval", seconds=settings_model.status_poll_interval_s(),
        id="status_poller", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        lambda: cv112_poll_once(scheduler), "interval", seconds=settings_model.cv112_poll_interval_s(),
        id="cv112_poller", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        log_retention_run_once, "cron", hour=3, minute=0,
        id="log_retention", max_instances=1, coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler arrancado (status_poller + cv112_poller + log_retention)")


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
