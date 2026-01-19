## Ziel
Ein zentrales System verwaltet Events und schaltet zwei Funktionen einzeln frei:

- **Kassensystem** mit Bestell-Tracking und Statistik
- **Shotcounter** zum Erfassen, welches Team die meisten Shots konsumiert

## Setup
1. **Abhängigkeiten installieren**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Datenbank initialisieren (SQLite)** – beim ersten Start automatisch via SQLAlchemy:
   ```bash
   flask --app app shell -c "from app import db; db.create_all()"
   ```

3. **Entwicklung starten**
   ```bash
   flask --app app run --debug
   ```
   oder mit Makefile:
   ```bash
   make run
   ```

## Nutzung
1. **Event anlegen & aktivieren** im Adminbereich (`/admin`).
   - Kassensystem und/oder Shotcounter separat aktivierbar.
   - Gemeinsame und systemspezifische Einstellungen als JSON speicherbar (z. B. Button-Setup oder Shotcounter-Parameter).
2. **Kasse** (`/cashier`): Artikel buchen, Warenkorb abschließen, Statistik unter `/cashier/stats` einsehen.
3. **Shotcounter** (`/shotcounter`): Teams anlegen und Shots pro Team verbuchen.

## Logging
Sauberes, rotierendes Logging unter `instance/logs/app.log` für alle relevanten Admin-, Kassen- und Shotcounter-Aktionen.

## Tests
Pytest deckt zentrale Routen ab:
```bash
pytest
```
oder
```bash
make test
```

## Raspberry Pi Deployment
Ein Skript für Autostart, Offline/Online-Updates, Backups und optionalen Kiosk-Modus liegt unter `scripts/pi_manage.sh`. Details und Schritte findest du in `docs/pi_deployment.md`.

## Makefile (Kurzbefehle)
- `make install` – Abhängigkeiten installieren
- `make run` – Entwicklungserver starten
- `make test` – Pytest-Suite ausführen
