from amstabase.db import get_db, get_setting


def test_index_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_first_registration_creates_admin(app, auth):
    response = auth.register()
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    with app.app_context():
        user = get_db().execute("SELECT username, role FROM users").fetchone()
        assert user["username"] == "admin"
        assert user["role"] == "Admin"


def test_later_registration_creates_service(app, auth):
    auth.register("admin")
    auth.register("service")

    with app.app_context():
        role = get_db().execute(
            "SELECT role FROM users WHERE username = 'service'"
        ).fetchone()["role"]
        assert role == "Service"


def test_registration_validates_input(client):
    response = client.post(
        "/register", data={"username": "user", "password": "short"}
    )
    assert response.status_code == 200
    assert "mindestens 8 Zeichen" in response.get_data(as_text=True)


def test_login_and_logout(auth):
    auth.register()
    invalid = auth.login(password="wrong-password")
    assert "Ungültige Anmeldedaten" in invalid.get_data(as_text=True)

    response = auth.login()
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    response = auth.logout()
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_admin_can_persistently_disable_registration(app, auth, client):
    auth.register()
    auth.login()
    response = client.post("/admin/registration/toggle")
    assert response.status_code == 302

    with app.app_context():
        assert get_setting("registration_enabled") == "false"

    auth.logout()
    response = client.get("/register")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
