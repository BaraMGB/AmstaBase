# AmstaBase

AmstaBase ist eine Flask-Anwendung zur internen Verwaltung von Rezepten, Zutaten, Fotos und Rollen.

## Funktionen

- Rezeptverwaltung mit Zutaten, Rich-Text-Zubereitung und mehreren Fotos
- KI-gestützter Rezeptimport aus öffentlicher URL oder Textblock
- Rollenbasierte Rechte für Admin, Editor, Viewer und Service
- Persistente Einstellungen für Registrierung und LLM-Anbindung
- SQLite-Datenbank mit automatischer Initialisierung und versionierter Migration
- Automatisierte Tests für Authentifizierung, Rechte, CRUD, Migrationen und Hilfsfunktionen

## Schnellstart

Voraussetzung ist Python 3.10 oder neuer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
flask --app app run --debug
```

Anschließend ist die Anwendung unter <http://127.0.0.1:5000> erreichbar. Der zuerst registrierte Benutzer erhält automatisch die Rolle `Admin`; weitere Registrierungen erhalten `Service`.

Die Datenbank und Uploads werden standardmäßig unter `instance/` angelegt. Ein manuelles Initialisieren ist möglich, aber normalerweise nicht nötig:

```bash
flask --app app init-db
```

## Konfiguration

| Variable | Standard | Bedeutung |
|---|---|---|
| `SECRET_KEY` | `dev-change-me` | Signiert Sessions; in Produktion zwingend ersetzen |
| `DATABASE_PATH` | `instance/amstabase.sqlite` | Pfad zur SQLite-Datenbank |
| `UPLOAD_FOLDER` | `instance/uploads` | Ablage hochgeladener Rezeptfotos |
| `OPENAI_API_KEY` | leer | Optionaler Bearer-Token als Fallback zur Admin-Eingabe |
| `OPENAI_API_KEY_FILE` | `instance/secrets/openai_api_key` | Geschützte Datei für den über die Admin-Oberfläche gesetzten Key |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `30` | Timeout für URL- und LLM-Anfragen |
| `RECIPE_SOURCE_MAX_CHARS` | `50000` | Maximale Textmenge, die an das LLM gesendet wird |
| `RECIPE_URL_MAX_BYTES` | `1000000` | Maximale Größe einer geladenen Rezeptseite |
| `SESSION_LIFETIME_MINUTES` | `30` | Gültigkeitsdauer einer Sitzung |
| `MAX_CONTENT_LENGTH` | `16777216` | Maximale Request-/Uploadgröße in Bytes |

## Projektstruktur

```text
amstabase/
├── __init__.py          # Application Factory
├── auth.py              # Registrierung und Login
├── admin.py             # Benutzer und Einstellungen
├── recipes.py           # Rezept-CRUD und Uploads
├── llm.py               # URL-Abruf und OpenAI-kompatible Rezeptstrukturierung
├── db.py                # SQLite-Lebenszyklus und Settings
├── permissions.py       # Rollen- und Rechteprüfung
├── services.py          # Wiederverwendbare Geschäftslogik
├── schema.sql           # Datenbankschema
├── templates/           # Nach Fachbereich gegliederte Templates
└── static/              # Styles, JavaScript und Icons
tests/                   # Pytest-Testpaket
docs/                    # Technische Detaildokumentation
app.py                   # Kompatibler WSGI-/Entwicklungs-Einstieg
pyproject.toml           # Paket-, Abhängigkeits- und Toolkonfiguration
```

## Rollen

| Rolle | Lesen | Erstellen | Bearbeiten/Löschen | Administration |
|---|:---:|:---:|:---:|:---:|
| Admin | ✓ | ✓ | ✓ | ✓ |
| Editor | ✓ | ✓ | ✓ | – |
| Viewer | ✓ | – | – | – |
| Service | ✓, reduzierte Detailansicht | – | – | – |

## KI-Rezeptimport

Der Administrator konfiguriert unter `/admin/` den vollständigen OpenAI-kompatiblen Chat-Completions-Endpunkt, den Modellnamen und optional den API-Key. Der über die Oberfläche eingegebene Key wird nicht in der Datenbank gespeichert, sondern in `instance/secrets/openai_api_key` mit Dateirechten `0600`. Er wird niemals wieder angezeigt und kann nur ersetzt oder gelöscht werden. `OPENAI_API_KEY` dient weiterhin als optionaler Fallback. Sobald ein API-Key verwendet wird, muss der Endpunkt HTTPS nutzen; keylose lokale Endpunkte dürfen weiterhin HTTP verwenden.

Die KI-Ausgabe wird nie direkt gespeichert. Sie erscheint zunächst im normalen Rezeptformular und muss vom Benutzer fachlich geprüft werden. Der eingegebene beziehungsweise von einer URL geladene Rezepttext wird an den konfigurierten externen KI-Dienst übertragen.

## Datenbankmigration

Beim ersten Start mit einer älteren Datenbank werden die nicht mehr verwendeten Rezeptfelder für Kategorie, Speisekarte und Preise entfernt. Vorher erzeugt die Anwendung neben der Datenbank automatisch eine vollständige Sicherung mit der Endung `.pre-v2.bak` sowie einen CSV-Export mit der Endung `.removed-recipe-fields.csv`. Beide Dateien erhalten restriktive Dateirechte und sollten gemäß der betrieblichen Aufbewahrungsrichtlinie gesichert werden.

## Tests und Qualität

```bash
pytest
pytest --cov=amstabase --cov-report=term-missing
ruff check .
```

Weitere Details stehen in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) und [docs/OPERATIONS.md](docs/OPERATIONS.md).
