from __future__ import annotations

from pathlib import Path

import pytest

from amstabase import create_app
from amstabase.auth import hash_password
from amstabase.db import get_db


@pytest.fixture
def app(tmp_path: Path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "OPENAI_API_KEY_FILE": str(tmp_path / "secrets" / "openai_api_key"),
        }
    )
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


class AuthActions:
    def __init__(self, client):
        self.client = client

    def register(self, username="admin", password="password123"):
        return self.client.post(
            "/register", data={"username": username, "password": password}
        )

    def login(self, username="admin", password="password123"):
        return self.client.post(
            "/login", data={"username": username, "password": password}
        )

    def logout(self):
        return self.client.post("/logout")


@pytest.fixture
def auth(client):
    return AuthActions(client)


@pytest.fixture
def user_factory(app):
    def create(username: str, role: str, password: str = "password123") -> int:
        with app.app_context():
            database = get_db()
            cursor = database.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hash_password(password), role),
            )
            database.commit()
            return cursor.lastrowid

    return create
