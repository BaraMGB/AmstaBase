"""Administrative user and application settings routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .db import get_db, get_setting, set_setting
from .permissions import ROLES, admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/", methods=("GET", "POST"))
@admin_required
def dashboard():
    if request.method == "POST":
        categories = [
            value.strip()
            for value in request.form.get("categories", "").split(",")
            if value.strip()
        ]
        set_setting("categories", ",".join(dict.fromkeys(categories)))
        flash("Kategorien wurden aktualisiert.", "success")
        return redirect(url_for("admin.dashboard"))

    users = get_db().execute("SELECT * FROM users ORDER BY username").fetchall()
    return render_template(
        "admin/dashboard.html",
        users=users,
        roles=ROLES,
        categories_string=get_setting("categories", ""),
        registration_enabled=get_setting("registration_enabled", "true") == "true",
    )


@bp.post("/users/<int:user_id>/role")
@admin_required
def edit_user_role(user_id: int):
    if current_user.id == user_id:
        flash("Du kannst deine eigene Rolle nicht ändern!", "danger")
        return redirect(url_for("admin.dashboard"))

    new_role = request.form.get("role")
    if new_role not in ROLES:
        flash("Ungültige Rolle.", "danger")
        return redirect(url_for("admin.dashboard"))

    database = get_db()
    database.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    database.commit()
    return redirect(url_for("admin.dashboard"))


@bp.post("/users/<int:user_id>/delete")
@admin_required
def delete_user(user_id: int):
    if current_user.id == user_id:
        flash("Du kannst dich nicht selbst löschen!", "danger")
        return redirect(url_for("admin.dashboard"))

    database = get_db()
    database.execute("DELETE FROM users WHERE id = ?", (user_id,))
    database.commit()
    return redirect(url_for("admin.dashboard"))


@bp.post("/registration/toggle")
@admin_required
def toggle_registration():
    enabled = get_setting("registration_enabled", "true") == "true"
    set_setting("registration_enabled", "false" if enabled else "true")
    flash(
        "Registrierung wurde aktiviert." if not enabled else "Registrierung wurde deaktiviert.",
        "success",
    )
    return redirect(url_for("admin.dashboard"))
