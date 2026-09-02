from flask import Blueprint, Response

from routes.auth import login_required
from services.changelog import render_html

bp = Blueprint("changelog", __name__, url_prefix="/changelog")


@bp.route("/content")
@login_required
def content():
    return Response(render_html(), mimetype="text/html")
