import csv
import sqlite3
import stat
from pathlib import Path

from amstabase import create_app
from amstabase.db import get_db

LEGACY_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    in_menu INTEGER NOT NULL DEFAULT 0,
    menu_description TEXT,
    allergens TEXT,
    approximate_cost REAL,
    selling_price REAL,
    created_by TEXT,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_by TEXT,
    edited_time TIMESTAMP,
    instructions TEXT,
    notes TEXT
);
CREATE TABLE ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    quantity REAL,
    unit TEXT,
    ingredient_name TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
CREATE TABLE photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def test_legacy_recipe_columns_are_migrated_with_backups(tmp_path: Path):
    database_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database_path) as database:
        database.executescript(LEGACY_SCHEMA)
        database.execute(
            """
            INSERT INTO recipes
                (id, name, category, in_menu, menu_description, allergens,
                 approximate_cost, selling_price, created_by, instructions, notes)
            VALUES (7, 'Suppe', 'Suppen', 1, 'Cremig', 'Milch', 2.5, 8.9,
                    'admin', '<p>Kochen</p>', 'Warm')
            """
        )
        database.execute(
            """
            INSERT INTO ingredients
                (recipe_id, quantity, unit, ingredient_name, display_order)
            VALUES (7, 200, 'g', 'Kartoffeln', 1)
            """
        )
        database.execute(
            "INSERT INTO photos (recipe_id, filename) VALUES (7, 'photo.jpg')"
        )
        database.execute(
            "INSERT INTO settings (key, value) VALUES ('categories', 'Suppen')"
        )
        database.commit()

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "migration-test",
            "DATABASE": str(database_path),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "OPENAI_API_KEY_FILE": str(tmp_path / "secrets" / "openai_api_key"),
        }
    )

    with app.app_context():
        database = get_db()
        columns = {
            row["name"] for row in database.execute("PRAGMA table_info(recipes)")
        }
        assert columns == {
            "id",
            "name",
            "allergens",
            "created_by",
            "created_time",
            "edited_by",
            "edited_time",
            "instructions",
            "notes",
        }
        recipe = database.execute("SELECT * FROM recipes WHERE id = 7").fetchone()
        assert recipe["name"] == "Suppe"
        assert recipe["allergens"] == "Milch"
        assert database.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0] == 1
        assert database.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 1
        assert database.execute("PRAGMA foreign_key_check").fetchall() == []
        assert database.execute("PRAGMA user_version").fetchone()[0] == 2
        assert database.execute(
            "SELECT value FROM settings WHERE key = 'categories'"
        ).fetchone() is None

    backup_path = tmp_path / "legacy.sqlite.pre-v2.bak"
    export_path = tmp_path / "legacy.sqlite.removed-recipe-fields.csv"
    assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(export_path.stat().st_mode) == 0o600

    with sqlite3.connect(backup_path) as backup:
        assert backup.execute(
            "SELECT category, selling_price FROM recipes WHERE id = 7"
        ).fetchone() == ("Suppen", 8.9)

    with export_path.open(encoding="utf-8", newline="") as export_file:
        rows = list(csv.DictReader(export_file))
    assert rows == [
        {
            "id": "7",
            "name": "Suppe",
            "category": "Suppen",
            "in_menu": "1",
            "menu_description": "Cremig",
            "approximate_cost": "2.5",
            "selling_price": "8.9",
        }
    ]
