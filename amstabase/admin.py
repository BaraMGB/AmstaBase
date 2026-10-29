"""Administrative user and application settings routes."""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .db import get_db, get_setting, set_setting
from .llm import (
    DEFAULT_LLM_ENDPOINT,
    DEFAULT_LLM_MODEL,
    delete_openai_api_key,
    get_openai_api_key,
    is_http_url,
    is_https_url,
    openai_api_key_source,
    save_openai_api_key,
)
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
        llm_endpoint=get_setting("llm_endpoint", DEFAULT_LLM_ENDPOINT),
        llm_model=get_setting("llm_model", DEFAULT_LLM_MODEL),
        llm_api_key_source=openai_api_key_source(),
    )


@bp.post("/llm-settings")
@admin_required
def update_llm_settings():
    endpoint = request.form.get("llm_endpoint", "").strip()
    model = request.form.get("llm_model", "").strip()
    if not is_http_url(endpoint):
        flash("Der LLM-Endpunkt muss eine gültige HTTP- oder HTTPS-URL sein.", "danger")
    elif get_openai_api_key() and not is_https_url(endpoint):
        flash("Ein konfigurierter API-Key darf nur mit HTTPS verwendet werden.", "danger")
    elif not model:
        flash("Ein LLM-Modell ist erforderlich.", "danger")
    else:
        set_setting("llm_endpoint", endpoint)
        set_setting("llm_model", model)
        flash("LLM-Einstellungen wurden gespeichert.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/llm-api-key")
@admin_required
def update_llm_api_key():
    action = request.form.get("action", "save")
    if action == "delete":
        delete_openai_api_key()
        if current_app.config.get("OPENAI_API_KEY", "").strip():
            flash("Admin-Key gelöscht; der Key aus der Umgebung ist wieder aktiv.", "success")
        else:
            flash("API-Key wurde gelöscht.", "success")
    else:
        endpoint = get_setting("llm_endpoint", DEFAULT_LLM_ENDPOINT) or DEFAULT_LLM_ENDPOINT
        if not is_https_url(endpoint):
            flash("Ein API-Key kann nur für einen HTTPS-Endpunkt gespeichert werden.", "danger")
            return redirect(url_for("admin.dashboard"))
        try:
            save_openai_api_key(request.form.get("llm_api_key", ""))
        except (OSError, ValueError) as error:
            current_app.logger.warning("Could not store LLM API key: %s", error)
            flash(str(error), "danger")
        else:
            flash("API-Key wurde sicher als Serverdatei gespeichert.", "success")
    return redirect(url_for("admin.dashboard"))


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
