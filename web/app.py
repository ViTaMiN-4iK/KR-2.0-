"""Flask-приложение веб-интерфейса UEBA-системы."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
)
import httpx
from loguru import logger


def create_app() -> Flask:
    """Фабрика Flask-приложения."""
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", "dev-secret-key-change-in-production"
    )
    app.config["API_BASE_URL"] = os.environ.get("API_BASE_URL", "http://localhost:8000")

    # Регистрация фильтров Jinja
    import web.filters as filters
    filters.register(app)

    # Регистрация blueprints
    import web.routes.dashboard as dashboard_module
    import web.routes.alerts as alerts_module
    import web.routes.users as users_module
    app.register_blueprint(dashboard_module.dashboard_bp)
    app.register_blueprint(alerts_module.alerts_bp)
    app.register_blueprint(users_module.users_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
