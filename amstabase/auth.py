"""Registration, login and logout routes."""

from __future__ import annotations

import logging
import sqlite3

import bcrypt
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .db import get_db, get_setting
from .extensions import login_manager
from .models import User

bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


def _user_from_row(row: sqlite3.Row) -> User:
    return User(user_id=row["id"], username=row["username"], role=row["role"])


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def check_password(password: str, password_hash: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), bytes(password_hash))
    except (TypeError, ValueError):
        return False


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_from_row(row) if row else None


@bp.route("/register", methods=("GET", "POST"))
def register():
    if get_setting("registration_enabled", "true") != "true":
        flash("Registrierung ist derzeit deaktiviert.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        error = None

        if not username:
            error = "Ein Benutzername ist erforderlich."
        elif len(password.encode("utf-8")) < 8:
            error = "Das Passwort muss mindestens 8 Zeichen lang sein."
        elif len(password.encode("utf-8")) > 72:
            error = "Das Passwort darf höchstens 72 UTF-8-Bytes lang sein."

        if error is None:
            database = get_db()
            user_count = database.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            role = "Admin" if user_count == 0 else "Service"
            try:
                database.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    (username, hash_password(password), role),
                )
                database.commit()
            except sqlite3.IntegrityError:
                error = "Benutzername existiert bereits."
            else:
                flash("Registrierung erfolgreich. Sie können sich jetzt einloggen.", "success")
                return redirect(url_for("auth.login"))

        flash(error, "danger")

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if current_user.is_authenticated:
        return redirect(url_for("recipes.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if row and check_password(password, row["password"]):
            login_user(_user_from_row(row))
            logger.info("User %s logged in successfully.", username)
            return redirect(url_for("recipes.index"))

        logger.warning(
            "Failed login attempt for username %s from IP %s",
            username,
            request.remote_addr,
        )
        flash("Ungültige Anmeldedaten", "danger")

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info("User %s logged out.", username)
    return redirect(url_for("auth.login"))
