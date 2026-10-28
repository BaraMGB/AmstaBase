# AmstaBase

AmstaBase ist eine Flask-Anwendung zur internen Verwaltung von Rezepten, Zutaten, Fotos, Rollen und einer öffentlichen Speisekarte. Speisekarten können zusätzlich als PDF exportiert werden.

## Funktionen

- Rezeptverwaltung mit Zutaten, Rich-Text-Zubereitung und mehreren Fotos
- Rollenbasierte Rechte für Admin, Editor, Viewer und Service
- Öffentliche, nach Kategorien sortierte Speisekarte
- PDF-Export über WeasyPrint
- Persistente Einstellungen für Kategorien und Registrierung
- SQLite-Datenbank mit automatischer, nicht destruktiver Initialisierung
- Automatisierte Tests für Authentifizierung, Rechte, CRUD, Menü und Hilfsfunktionen

## Schnellstart

Voraussetzungen: Python 3.10 oder neuer. WeasyPrint kann je nach Betriebssystem zusätzliche native Bibliotheken benötigen.

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
| `MENU_PDF_PATH` | `instance/generated/speisekarte.pdf` | Ziel des PDF-Exports |
| `SESSION_LIFETIME_MINUTES` | `30` | Gültigkeitsdauer einer Sitzung |
| `MAX_CONTENT_LENGTH` | `16777216` | Maximale Request-/Uploadgröße in Bytes |

## Projektstruktur

```text
amstabase/
├── __init__.py          # Application Factory
├── auth.py              # Registrierung und Login
├── admin.py             # Benutzer und Einstellungen
├── recipes.py           # Rezept-CRUD und Uploads
├── menu.py              # Öffentliche Speisekarte und PDF
├── db.py                # SQLite-Lebenszyklus und Settings
├── permissions.py       # Rollen- und Rechteprüfung
├── services.py          # Wiederverwendbare Geschäftslogik
├── schema.sql           # Datenbankschema
├── templates/           # Nach Fachbereich gegliederte Templates
└── static/              # Styles, JavaScript, Fonts und Icons
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

Die öffentliche Speisekarte unter `/menu` benötigt keinen Login.

## Tests und Qualität

```bash
pytest
pytest --cov=amstabase --cov-report=term-missing
ruff check .
```

Weitere Details stehen in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) und [docs/OPERATIONS.md](docs/OPERATIONS.md).
