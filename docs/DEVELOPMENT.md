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
| GET | `/admin/` | Admin | Administration |
| POST | `/admin/llm-settings` | Admin | LLM-Endpunkt und Modell speichern |
| POST | `/admin/llm-api-key` | Admin | API-Key als geschützte Serverdatei setzen/löschen |

## Testaufbau

`tests/conftest.py` erzeugt pro Test eine temporäre Datenbank und Uploadablage. Dadurch greifen Tests weder auf Entwicklungs- noch Produktionsdaten zu. Hilfsfunktionen registrieren und authentifizieren Testbenutzer über dieselben HTTP-Routen wie ein Browser.

Testgruppen:

- `test_auth.py`: Registrierung, Rollenvergabe, Login, persistenter Registrierungsschalter
- `test_permissions.py`: anonyme Zugriffe und Rollenmatrix
- `test_recipes.py`: Erstellen, Fuzzy-Suchdaten, Feldreihenfolge, HTML-Bereinigung, Bearbeiten, Löschen und Uploads
- `test_import.py`: Import-Workflow und Formularübergabe
- `test_migrations.py`: Legacy-Schema, Backups und Datenübernahme
- `test_llm.py`: LLM-Protokoll, Normalisierung und URL-Schutz
- `test_services.py`: isolierte Geschäftslogik

Ausführung:

```bash
pytest
pytest --cov=amstabase --cov-report=term-missing
pytest --cov=amstabase --cov-report=html
ruff check .
```

Der Coverage-Lauf berücksichtigt Branches und muss mindestens 80 Prozent erreichen. Zusätzlich sichern gezielte Regressionstests die Migration, die entfernte Speisekartenroute, die KI-/Manuell-Auswahl und die Reihenfolge der Formular- und Detailfelder ab.

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

`schema.sql` beschreibt Neuinstallationen. Bestehende Datenbanken werden vor der Schemaerstellung durch `db.migrate_db()` aktualisiert und über `PRAGMA user_version` versioniert. Bei weiteren inkompatiblen Schemaänderungen:

1. Migration mit Vorwärts- und Rückfallstrategie entwerfen.
2. Automatisches SQLite-Backup und gegebenenfalls einen fachlichen Export erstellen.
3. Migration zuerst gegen eine Kopie produktiver Daten testen.
4. IDs, Fremdschlüssel und Schema-Version durch Tests absichern.
