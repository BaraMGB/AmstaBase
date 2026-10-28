"""SQLite connection handling, schema initialization and settings access."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Return one SQLite connection per request/application context."""

    if "db" not in g:
        database = Path(current_app.config["DATABASE"])
        database.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    """Close the context-local database connection."""

    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    """Create missing tables and default settings without deleting data."""

    with current_app.open_resource("schema.sql") as schema_file:
        get_db().executescript(schema_file.read().decode("utf-8"))
    get_db().commit()


@click.command("init-db")
def init_db_command() -> None:
    """Create the database schema and default settings."""

    init_db()
    click.echo("Datenbank wurde initialisiert.")


def get_setting(key: str, default: str | None = None) -> str | None:
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    get_db().execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    get_db().commit()


def get_categories() -> list[str]:
    categories = get_setting("categories", "") or ""
    return [category.strip() for category in categories.split(",") if category.strip()]


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
