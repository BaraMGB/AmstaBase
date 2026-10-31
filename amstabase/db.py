"""SQLite connection handling, schema initialization and migrations."""

from __future__ import annotations

import csv
import fcntl
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import click
from flask import current_app, g

REMOVED_RECIPE_COLUMNS = (
    "category",
    "in_menu",
    "menu_description",
    "approximate_cost",
    "selling_price",
)
RECIPE_COLUMNS = (
    "id",
    "name",
    "allergens",
    "created_by",
    "created_time",
    "edited_by",
    "edited_time",
    "instructions",
    "notes",
)


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


def _table_exists(database: sqlite3.Connection, table: str) -> bool:
    return (
        database.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


@contextmanager
def _migration_lock():
    database_path = Path(current_app.config["DATABASE"])
    lock_path = database_path.with_name(f"{database_path.name}.migration.lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _backup_legacy_database(database: sqlite3.Connection) -> tuple[Path, Path]:
    database_path = Path(current_app.config["DATABASE"])
    backup_path = database_path.with_name(f"{database_path.name}.pre-v2.bak")
    export_path = database_path.with_name(
        f"{database_path.name}.removed-recipe-fields.csv"
    )

    descriptor = os.open(backup_path, os.O_WRONLY | os.O_CREAT, 0o600)
    os.close(descriptor)
    backup_path.chmod(0o600)
    with sqlite3.connect(backup_path) as backup:
        database.backup(backup)

    temporary_export = export_path.with_name(f".{export_path.name}.tmp")
    rows = database.execute(
        """
        SELECT id, name, category, in_menu, menu_description,
               approximate_cost, selling_price
        FROM recipes
        ORDER BY id
        """
    ).fetchall()
    try:
        descriptor = os.open(
            temporary_export, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as export_file:
            writer = csv.writer(export_file)
            writer.writerow(("id", "name", *REMOVED_RECIPE_COLUMNS))
            writer.writerows(rows)
        os.replace(temporary_export, export_path)
        export_path.chmod(0o600)
    finally:
        temporary_export.unlink(missing_ok=True)
    return backup_path, export_path


def migrate_db() -> None:
    """Migrate legacy recipe fields while preserving a database and CSV backup."""

    database = get_db()
    with _migration_lock():
        if not _table_exists(database, "recipes"):
            return

        columns = {
            row["name"]
            for row in database.execute("PRAGMA table_info(recipes)").fetchall()
        }
        removed_columns = set(REMOVED_RECIPE_COLUMNS)
        if not columns.intersection(removed_columns):
            return
        if not removed_columns.issubset(columns):
            missing = ", ".join(sorted(removed_columns - columns))
            raise RuntimeError(f"Unvollständiges Legacy-Schema; fehlende Spalten: {missing}")

        backup_path, export_path = _backup_legacy_database(database)
        current_app.logger.warning(
            "Migrating recipes table; backup=%s removed_fields=%s",
            backup_path,
            export_path,
        )

        database.execute("PRAGMA foreign_keys = OFF")
        try:
            database.execute("BEGIN IMMEDIATE")
            database.execute(
                """
                CREATE TABLE recipes_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    allergens TEXT,
                    created_by TEXT,
                    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    edited_by TEXT,
                    edited_time TIMESTAMP,
                    instructions TEXT,
                    notes TEXT
                )
                """
            )
            columns_sql = ", ".join(RECIPE_COLUMNS)
            database.execute(
                f"INSERT INTO recipes_migrated ({columns_sql}) "
                f"SELECT {columns_sql} FROM recipes"
            )
            database.execute("DROP TABLE recipes")
            database.execute("ALTER TABLE recipes_migrated RENAME TO recipes")
            if _table_exists(database, "settings"):
                database.execute("DELETE FROM settings WHERE key = 'categories'")
            database.execute("PRAGMA user_version = 2")

            violations = database.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError("Die Datenbankmigration verletzt Fremdschlüssel.")
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.execute("PRAGMA foreign_keys = ON")


def init_db() -> None:
    """Migrate existing data and create missing tables and default settings."""

    migrate_db()
    with current_app.open_resource("schema.sql") as schema_file:
        get_db().executescript(schema_file.read().decode("utf-8"))
    get_db().commit()


@click.command("init-db")
def init_db_command() -> None:
    """Migrate and initialize the database schema."""

    init_db()
    click.echo("Datenbank wurde initialisiert und migriert.")


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


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
