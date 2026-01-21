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
   Für Entwicklung/Tests:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Datenbank initialisieren (SQLite)** – beim ersten Start automatisch via SQLAlchemy:
   ```bash
   python -c "from app import app, db; app.app_context().push(); db.create_all()"
   ```

3. **Entwicklung starten**
   ```bash
   flask --app app run --debug
   ```
   Zugriff von anderen Geräten im LAN:
   ```bash
   flask --app app run --host 0.0.0.0 --port 8000
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

Kurzüberblick:
- **Service & Autostart** (systemd):
  ```bash
  sudo ./scripts/pi_manage.sh write-service --port 8000
  sudo ./scripts/pi_manage.sh enable-service
  ```
  Der Dienst läuft als System-User `kassensystem` mit grundlegenden Hardening-Optionen. Das Env-File liegt unter `/etc/kassensystem.env`.
- **Env-Config**:
  - `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` werden beim ersten Schreiben gesetzt.
  - `BACKUP_DIR` ist standardmäßig `instance/backups` im Repo (anpassbar).
  - `GUNICORN_WORKERS` steuert die Worker-Anzahl (Default 2).
- **Backups** (täglich per systemd timer):
  ```bash
  sudo ./scripts/pi_manage.sh write-backup
  sudo ./scripts/pi_manage.sh enable-backup
  ```
- **Updates**:
  ```bash
  sudo ./scripts/pi_manage.sh update --branch main
  ```
  Offline:
  ```bash
  sudo ./scripts/pi_manage.sh update --offline
  ```
- **Kiosk** (Chromium):
  ```bash
  sudo ./scripts/pi_manage.sh write-kiosk
  sudo ./scripts/pi_manage.sh enable-kiosk
  ```
  Optional `KIOSK_URL` in `/etc/kassensystem.env` setzen.

Offline-Wheels vorbereiten (einmalig mit Internet):
```bash
pip download -r requirements.txt -d wheels/
pip download -r requirements-dev.txt -d wheels/
```

## Makefile (Kurzbefehle)
- `make install` – Abhängigkeiten installieren
- `make run` – Entwicklungserver starten
- `make test` – Pytest-Suite ausführen
