# Entwicklung und Tests

## Entwicklungsumgebung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
flask --app app run --debug
```

Die Factory kann in Tests oder Skripten direkt verwendet werden:

```python
from amstabase import create_app

app = create_app({"TESTING": True, "DATABASE": "/tmp/amstabase-test.sqlite"})
```

## Wichtige Routen

| Methode | Pfad | Zugriff | Zweck |
|---|---|---|---|
| GET/POST | `/register` | öffentlich, falls aktiviert | Benutzer anlegen |
| GET/POST | `/login` | öffentlich | Anmeldung |
| POST | `/logout` | angemeldet | Sitzung beenden |
| GET | `/` | angemeldet | Rezeptsuche und Übersicht |
| GET/POST | `/new_recipe` | Admin/Editor | Rezept anlegen |
| GET/POST | `/import_recipe` | Admin/Editor | Rezept per URL oder Text strukturieren |
| GET | `/recipe/<id>` | angemeldet | Rezeptdetails |
| GET/POST | `/edit_recipe/<id>` | Admin/Editor | Rezept bearbeiten |
| POST | `/delete_recipe/<id>` | Admin/Editor | Rezept löschen |
| GET | `/menu` | öffentlich | veröffentlichte Speisekarte |
| GET/POST | `/admin/` | Admin | Administration |
| POST | `/admin/llm-settings` | Admin | LLM-Endpunkt und Modell speichern |
| POST | `/admin/llm-api-key` | Admin | API-Key als geschützte Serverdatei setzen/löschen |

## Testaufbau

`tests/conftest.py` erzeugt pro Test eine temporäre Datenbank und Uploadablage. Dadurch greifen Tests weder auf Entwicklungs- noch Produktionsdaten zu. Hilfsfunktionen registrieren und authentifizieren Testbenutzer über dieselben HTTP-Routen wie ein Browser.

Testgruppen:

- `test_auth.py`: Registrierung, Rollenvergabe, Login, persistenter Registrierungsschalter
- `test_permissions.py`: anonyme Zugriffe und Rollenmatrix
- `test_recipes.py`: Erstellen, HTML-Bereinigung, Bearbeiten, Löschen und Uploads
- `test_menu.py`: Filterung der öffentlichen Speisekarte
- `test_import.py`: Import-Workflow und Formularübergabe
- `test_llm.py`: LLM-Protokoll, Normalisierung und URL-Schutz
- `test_services.py`: isolierte Geschäftslogik

Ausführung:

```bash
pytest
pytest --cov=amstabase --cov-report=html
ruff check .
```

## Konventionen

- Neue Views gehören in den fachlich passenden Blueprint.
- SQL-Verbindungen immer über `get_db()` beziehen.
- Rechte nie nur im Template verstecken; jede schreibende View benötigt einen Decorator.
- Vom Benutzer geliefertes HTML vor Speicherung bereinigen.
- Dateisystempfade aus `current_app.config` lesen, nicht hart codieren.
- Externe HTTP-Aufrufe in Tests immer mocken; Tests dürfen keine echten LLM-Kosten verursachen.
- POST-Formulare müssen ein `csrf_token` enthalten; CSRF ist nur in isolierten Tests deaktiviert.
- Änderungen an Routen durch HTTP-Tests absichern.

## Datenbankänderungen

`schema.sql` ist für Erstinstallation und additive Defaults ausgelegt. Es ist kein Ersatz für Migrationen. Bei inkompatiblen Schemaänderungen:

1. Migration mit Vorwärts- und Rückfallstrategie entwerfen.
2. Backup mit laufendem SQLite-Backup erstellen.
3. Migration zuerst gegen eine Kopie produktiver Daten testen.
4. Schema-Version in `settings` oder über Alembic verwalten.
