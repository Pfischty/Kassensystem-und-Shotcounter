## Ziel
Ein Programm entwickeln, das misst, welches Team bei einem Fest die meisten Shots konsumiert hat.

## Setup
1. **Abhängigkeiten installieren**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Datenbank initialisieren (SQLite)**
   ```bash
   python - <<'PY'
   from app import db
   db.create_all()
   PY
   ```

3. **Entwicklung starten (Socket.IO-Server)**
   ```bash
   flask --app app run --debug
   ```
   oder mit Makefile:
   ```bash
   make run
   ```

## Tests
Führt einen kleinen Pytest-Satz mit den wichtigsten Routen aus:
```bash
pytest
```
oder
```bash
make test
```

## Makefile (Kurzbefehle)
- `make install` – Abhängigkeiten installieren
- `make run` – Entwicklungserver starten
- `make test` – Pytest-Suite ausführen

## Routenüberblick
- `/registration`: Ermöglicht die Registrierung neuer Teams und sichert diese in der Datenbank.
- `/punkte`: Hier können Punkte zu bereits registrierten Teams hinzugefügt werden.
- `/leaderboard`: Zeigt eine Rangliste der aktuellen Ergebnisse an.
- `/admin`: Ermöglicht die Korrektur von Fehlern.
- `/team/delete/<id>` und `/team/update/<id>`: Verwaltungsaktionen für Teams.
- `/preisliste`: Zeigt eine Preisliste an (noch unvollständig).

## Hinweis zur Live-Aktualisierung
Flask-SocketIO sendet beim Hinzufügen oder Anpassen von Teams ein `update_leaderboard`-Event, sodass verbundene Clients ohne Polling aktualisiert werden können.
