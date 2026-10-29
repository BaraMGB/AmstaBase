PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS recipes (
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

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    quantity REAL,
    unit TEXT,
    ingredient_name TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password BLOB NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Admin', 'Editor', 'Viewer', 'Service'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO settings (key, value)
VALUES ('categories', 'Vorspeisen,Suppen,Pasta,Hauptgerichte,Dessert,intern');

INSERT OR IGNORE INTO settings (key, value)
VALUES ('registration_enabled', 'true');

INSERT OR IGNORE INTO settings (key, value)
VALUES ('llm_endpoint', 'https://api.openai.com/v1/chat/completions');

INSERT OR IGNORE INTO settings (key, value)
VALUES ('llm_model', 'gpt-4o-mini');
