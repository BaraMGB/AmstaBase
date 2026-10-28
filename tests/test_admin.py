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
