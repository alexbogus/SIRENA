import time
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

import config
import models.settings as settings_model
import services.api_tokens as api_tokens_service

bp = Blueprint("auth", __name__)
logger = config.get_logger("auth")

# Rate-limit simple en memoria: contraseña única compartida, así que
# conviene un mínimo de protección ante fuerza bruta.
_failed_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW_S = 300


def _too_many_attempts(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _failed_attempts.get(ip, []) if now - t < _WINDOW_S]
    _failed_attempts[ip] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def _register_failure(ip: str) -> None:
    _failed_attempts.setdefault(ip, []).append(time.time())


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def require_api_token(view):
    """Análogo a login_required pero para clientes servidor-a-servidor
    (n8n, etc.): responde JSON en vez de redirigir a /login. Deja el token
    verificado en flask.g.api_token para la vista."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {"error": "Falta la cabecera Authorization: Bearer <token>."}, 401
        token_info = api_tokens_service.verify(auth_header[len("Bearer "):].strip())
        if token_info is None:
            logger.warning(f"Intento de acceso a la API con token inválido/revocado desde {request.remote_addr}")
            return {"error": "Token inválido o revocado."}, 401
        g.api_token = token_info
        return view(*args, **kwargs)
    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not settings_model.is_password_set():
        return redirect(url_for("auth.setup"))

    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if _too_many_attempts(ip):
            flash("Demasiados intentos fallidos, espera unos minutos.", "error")
            return render_template("login.html")
        password = request.form.get("password", "")
        if settings_model.check_password(password):
            session["authenticated"] = True
            logger.info(f"Login correcto desde {ip}")
            return redirect(url_for("dashboard.index"))
        _register_failure(ip)
        logger.warning(f"Login fallido desde {ip}")
        flash("Contraseña incorrecta.", "error")
    return render_template("login.html")


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    if settings_model.is_password_set():
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "error")
        elif password != confirm:
            flash("Las contraseñas no coinciden.", "error")
        else:
            settings_model.set_password(password)
            flash("Contraseña establecida. Ya puedes entrar.", "success")
            return redirect(url_for("auth.login"))
    return render_template("setup.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
