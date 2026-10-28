"""AmstaBase Flask application factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, session

load_dotenv()

from . import admin, auth, db, menu, recipes  # noqa: E402
from .config import Config  # noqa: E402
from .extensions import login_manager  # noqa: E402
from .permissions import has_permission  # noqa: E402


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure an AmstaBase application instance."""

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config.from_mapping(
        DATABASE=os.getenv("DATABASE_PATH", str(Path(app.instance_path) / "amstabase.sqlite")),
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(Path(app.instance_path) / "uploads")),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    login_manager.init_app(app)
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(recipes.bp)
    app.register_blueprint(menu.bp)

    @app.before_request
    def make_session_permanent() -> None:
        session.permanent = True

    @app.context_processor
    def inject_permissions() -> dict:
        return {"has_permission": has_permission}

    if app.config.get("AUTO_INIT_DB", True):
        with app.app_context():
            db.init_db()

    if app.config["SECRET_KEY"] == "dev-change-me" and not app.testing:
        app.logger.warning("Using development SECRET_KEY; set SECRET_KEY in production.")

    return app
