# Technische Architektur

## Überblick

AmstaBase ist als serverseitig gerenderte Flask-Anwendung aufgebaut. Die `create_app`-Factory in `amstabase/__init__.py` erzeugt vollständig konfigurierte App-Instanzen und erlaubt dadurch isolierte Tests sowie unterschiedliche Laufzeitkonfigurationen.

```text
Browser
  │ HTTP / Formulare
  ▼
Flask Blueprints ──► Services / Berechtigungen
  │                         │
  ├── Jinja2 Templates      ├── bcrypt / bleach
  ├── Upload-Dateisystem    └── URL-Abruf / OpenAI-kompatibles LLM
  ▼
SQLite
```

## Module und Verantwortlichkeiten

- `auth.py`: Benutzer laden, Passwort-Hashing, Registrierung, Login und Logout.
- `admin.py`: Rollenverwaltung, Kategorien und Registrierungsschalter.
- `recipes.py`: Suche, Detailansichten, Erstellen, Bearbeiten, Löschen und Fotoverwaltung.
- `menu.py`: öffentliche, nach Kategorien geordnete Speisekarte.
- `llm.py`: sicherheitsbegrenzter URL-Abruf, LLM-Anfrage, JSON-Validierung und Normalisierung.
- `db.py`: eine SQLite-Verbindung pro Flask-Kontext, Schemaaufbau, Einstellungen.
- `permissions.py`: zentrale Rollenmatrix und Decorators für Autorisierung.
- `services.py`: Formularparser, HTML-Bereinigung und Dateitypprüfung.
- `extensions.py`: gemeinsam genutzte Flask-Erweiterungen ohne Bindung an eine konkrete App.

Blueprints kapseln die Fachbereiche. Externe URL-Pfade bleiben bewusst einfach (`/`, `/login`, `/recipe/<id>`, `/menu`), während interne Endpoints eindeutig benannt sind, zum Beispiel `recipes.show_recipe`.

## Request-Lebenszyklus

1. Die Factory lädt Konfiguration und erstellt Laufzeitverzeichnisse.
2. `db.init_db()` legt fehlende Tabellen und Defaults nicht destruktiv an.
3. Flask-Login rekonstruiert den Benutzer über `auth.load_user`.
4. `login_required` beziehungsweise `permission_required` prüft Zugriff vor der View.
5. `db.get_db()` öffnet bei Bedarf genau eine Verbindung für den aktuellen Kontext.
6. Nach dem Request schließt `db.close_db()` die Verbindung automatisch.

## Datenmodell

### `users`

- `id`: Primärschlüssel
- `username`: eindeutiger Loginname
- `password`: bcrypt-Hash als BLOB
- `role`: `Admin`, `Editor`, `Viewer` oder `Service`

### `recipes`

Enthält Stammdaten, Preise, Menüstatus, bereinigte HTML-Zubereitung sowie Erstellungs- und Änderungsmetadaten.

### `ingredients`

N:1-Beziehung zu `recipes`. `display_order` bewahrt die Reihenfolge aus dem Formular. Zutaten können über Namensgleichheit in der Detailansicht auf ein anderes Rezept verweisen.

### `photos`

N:1-Beziehung zu `recipes`. In SQLite wird nur der zufällig erzeugte Dateiname gespeichert; Binärdaten liegen im konfigurierten Upload-Verzeichnis.

### `settings`

Ein Key-Value-Speicher für veränderliche Anwendungseinstellungen. Aktuell verwendet:

- `categories`: kommagetrennte, geordnete Kategorien
- `registration_enabled`: `true` oder `false`
- `llm_endpoint`: vollständige URL eines OpenAI-kompatiblen Chat-Completions-Endpunkts
- `llm_model`: an den Endpunkt übergebener Modellname

## Sicherheit

- Passwörter werden ausschließlich als bcrypt-Hash gespeichert.
- Schreibende Rezept- und Adminrouten sind serverseitig rollenbasiert geschützt.
- Rich-Text wird vor dem Speichern durch `bleach` auf erlaubte Tags und Attribute reduziert.
- Uploadnamen werden nicht übernommen. Ein kryptografisch zufälliger Name verhindert Pfadmanipulationen und Kollisionen.
- Uploadgröße und erlaubte Dateiendungen sind begrenzt.
- Beim Rezeptimport sind URL-Schemata, Antworttyp, Weiterleitungen und Downloadgröße begrenzt; private und lokale Zieladressen werden blockiert.
- Der LLM-API-Key wird nicht in SQLite gespeichert. Die Admin-Oberfläche schreibt ihn atomar in eine Datei mit Modus `0600`; alternativ dient die Laufzeitumgebung als Fallback.
- Der gespeicherte Key wird nie an den Browser zurückgegeben oder protokolliert.
- Alle schreibenden Browserformulare sind durch Flask-WTF gegen CSRF geschützt.
- Session-Cookies sind `HttpOnly` und `SameSite=Lax`.
- `SECRET_KEY` muss in Produktion zufällig gesetzt werden.

## LLM-Importfluss

1. Admin oder Editor gibt genau eine öffentliche URL oder einen Textblock ein.
2. URL-Inhalte werden serverseitig geladen, von Skripten und Styles bereinigt und größenbegrenzt.
3. Der Text wird mit einem strikt beschriebenen JSON-Schema an den administrativ konfigurierten Chat-Completions-Endpunkt gesendet.
4. Die Antwort wird als JSON validiert, auf bekannte Felder normalisiert und Rich-Text erneut mit `bleach` bereinigt.
5. Das Ergebnis füllt das normale Rezeptformular vor. Erst die explizite Bestätigung durch den Benutzer schreibt Daten in SQLite.

LLM-Ausgaben gelten grundsätzlich als nicht vertrauenswürdig. Insbesondere Mengen, Allergene und Zubereitung müssen vor dem Speichern geprüft werden.

## Persistenz und Transaktionen

Schreibende Views committen erst nach allen zugehörigen SQL-Operationen. SQLite-Fremdschlüssel werden pro Verbindung aktiviert. Das Schema nutzt `CREATE TABLE IF NOT EXISTS` und `INSERT OR IGNORE`, sodass ein App-Start keine vorhandenen Daten löscht. Schemaänderungen benötigen bei zukünftigen Versionen ein explizites Migrationskonzept, beispielsweise Alembic.
