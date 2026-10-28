"""Small domain models used by Flask-Login."""

from flask_login import UserMixin


class User(UserMixin):
    """Authenticated application user backed by the SQLite users table."""

    def __init__(self, user_id: int, username: str, role: str) -> None:
        self.id = user_id
        self.username = username
        self.role = role
