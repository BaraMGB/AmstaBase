import stat
from pathlib import Path

from amstabase.db import get_db, get_setting


def test_admin_dashboard_updates_categories(app, client, auth):
    auth.register()
    auth.login()

    response = client.get("/admin/")
    assert response.status_code == 200
    assert "Registrierung" in response.get_data(as_text=True)

    response = client.post(
        "/admin/", data={"categories": " Suppen, Dessert,Suppen, "}
    )
    assert response.status_code == 302
    with app.app_context():
        assert get_setting("categories") == "Suppen,Dessert"


def test_admin_can_update_llm_settings(app, client, auth):
    auth.register()
    auth.login()

    response = client.post(
        "/admin/llm-settings",
        data={
            "llm_endpoint": "https://llm.example/v1/chat/completions",
            "llm_model": "recipe-model",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        assert get_setting("llm_endpoint") == "https://llm.example/v1/chat/completions"
        assert get_setting("llm_model") == "recipe-model"


def test_admin_rejects_invalid_llm_endpoint(app, client, auth):
    auth.register()
    auth.login()
    client.post(
        "/admin/llm-settings",
        data={"llm_endpoint": "not-a-url", "llm_model": "model"},
    )
    with app.app_context():
        assert get_setting("llm_endpoint").startswith("https://")


def test_admin_rejects_http_endpoint_when_api_key_is_configured(app, client, auth):
    auth.register()
    auth.login()
    app.config["OPENAI_API_KEY"] = "secret"

    client.post(
        "/admin/llm-settings",
        data={"llm_endpoint": "http://llm.example/v1/chat/completions", "llm_model": "model"},
    )

    with app.app_context():
        assert get_setting("llm_endpoint").startswith("https://")


def test_admin_can_store_and_delete_api_key_file(app, client, auth):
    auth.register()
    auth.login()
    key_file = Path(app.config["OPENAI_API_KEY_FILE"])

    response = client.post(
        "/admin/llm-api-key",
        data={"llm_api_key": "sk-test-secret", "action": "save"},
    )
    assert response.status_code == 302
    assert key_file.read_text(encoding="utf-8") == "sk-test-secret"
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert "sk-test-secret" not in client.get("/admin/").get_data(as_text=True)

    response = client.post("/admin/llm-api-key", data={"action": "delete"})
    assert response.status_code == 302
    assert not key_file.exists()


def test_admin_can_change_and_delete_other_user(app, client, auth, user_factory):
    auth.register()
    auth.login()
    user_id = user_factory("employee", "Service")

    response = client.post(f"/admin/users/{user_id}/role", data={"role": "Editor"})
    assert response.status_code == 302
    with app.app_context():
        role = get_db().execute(
            "SELECT role FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0]
        assert role == "Editor"

    response = client.post(f"/admin/users/{user_id}/delete")
    assert response.status_code == 302
    with app.app_context():
        assert get_db().execute(
            "SELECT COUNT(*) FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0] == 0


def test_admin_cannot_change_own_role_or_assign_unknown_role(
    app, client, auth, user_factory
):
    auth.register()
    auth.login()
    other_id = user_factory("employee", "Service")

    client.post("/admin/users/1/role", data={"role": "Viewer"})
    client.post(f"/admin/users/{other_id}/role", data={"role": "Root"})

    with app.app_context():
        roles = {
            row["username"]: row["role"]
            for row in get_db().execute("SELECT username, role FROM users")
        }
        assert roles == {"admin": "Admin", "employee": "Service"}
