# Betrieb

## Produktionsstart

Für den produktiven Betrieb nicht den Flask-Entwicklungsserver verwenden:

```bash
source .venv/bin/activate
pip install -e '.[production]'
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export OPENAI_API_KEY="..."
gunicorn --workers 2 --bind 0.0.0.0:8000 app:app
```

Ein Reverse Proxy sollte TLS terminieren, Uploadgrößen passend begrenzen und statische Inhalte cachen. Da SQLite Schreibzugriffe serialisiert, ist eine kleine Workerzahl sinnvoll. Für hohe parallele Schreiblast sollte auf PostgreSQL und eine entsprechende Datenzugriffsschicht migriert werden.

## Persistente Daten

Gemeinsam zu sichern sind:

1. die Datei aus `DATABASE_PATH`,
2. das Verzeichnis aus `UPLOAD_FOLDER`,
3. falls verwendet die Datei aus `OPENAI_API_KEY_FILE`,
4. die produktive `.env` beziehungsweise das Secret-Management,
5. bei einer Schema-2-Migration die automatisch erzeugten Dateien `.pre-v2.bak` und `.removed-recipe-fields.csv`.

## Konsistentes Backup

SQLite nicht durch blindes Kopieren während Schreibzugriffen sichern. Empfohlen:

```bash
sqlite3 instance/amstabase.sqlite ".backup '/backup/amstabase-$(date +%F).sqlite'"
rsync -a instance/uploads/ /backup/uploads/
```

Alternativ kann der Dienst für das kurze Backup-Fenster angehalten werden. Wiederherstellung immer zunächst in einer separaten Umgebung testen.

## Aktualisierung

Vor einer Schema-Migration müssen alle laufenden App- und Worker-Prozesse gestoppt werden. Danach:

```bash
git pull
source .venv/bin/activate
pip install -e '.[production]'
pytest
flask --app app init-db
# Dienst anschließend kontrolliert neu starten
```

`init-db` führt erforderliche Schema-Migrationen aus. Beim erstmaligen Entfernen der alten Kategorie-, Speisekarten- und Preisfelder erzeugt die Anwendung automatisch eine vollständige `.pre-v2.bak`-Sicherung und einen `.removed-recipe-fields.csv`-Export neben der Datenbank. Trotzdem sollte vor dem Update zusätzlich ein externes Backup vorhanden sein. Nach dem Lauf müssen Logausgabe und `PRAGMA foreign_key_check` kontrolliert werden.

## Monitoring und Fehlerdiagnose

- Anwendungslogs werden über das Python-Logging auf Standardausgabe geschrieben.
- Fehlgeschlagene Logins erscheinen als Warnung, erfolgreiche als Information.
- Der Start warnt bei Verwendung des unsicheren Entwicklungs-`SECRET_KEY`.
- Schreibrechte für Datenbank- und Upload-Verzeichnis prüfen.
- Bei Importfehlern LLM-Endpunkt, Modell, Admin-Key beziehungsweise `OPENAI_API_KEY`, DNS und ausgehende HTTPS-Verbindungen prüfen.
- Die Secret-Datei muss dem Dienstbenutzer gehören und darf höchstens Dateirechte `0600` besitzen.
- Rezeptquellen und LLM-Anfragen können sensible Inhalte an externe Anbieter übertragen; Anbieter- und Datenschutzvorgaben beachten.

## Datenschutz und Aufbewahrung

Benutzernamen und Bearbeiterinformationen sind personenbezogene Betriebsdaten. Zugriff auf Backups, Logs und Datenbankdateien beschränken und eine zur Organisation passende Lösch- und Aufbewahrungsrichtlinie definieren.
