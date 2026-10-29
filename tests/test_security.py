from amstabase import create_app


def test_csrf_rejects_post_without_token(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "csrf-test-secret",
            "DATABASE": str(tmp_path / "csrf.sqlite"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "OPENAI_API_KEY_FILE": str(tmp_path / "secrets" / "openai_api_key"),
        }
    )
    client = app.test_client()

    assert 'name="csrf_token"' in client.get("/register").get_data(as_text=True)
    response = client.post(
        "/register", data={"username": "admin", "password": "password123"}
    )
    assert response.status_code == 400
