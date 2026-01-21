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

## Credentials Management
Die Admin-Zugangsdaten werden in einer separaten Datei `credentials.json` gespeichert, die **nicht ins Git-Repository** übernommen wird.

### Initiale Konfiguration
Beim ersten Start ist das System **unlocked** (ohne Passwortschutz). Du kannst im Adminbereich (`/admin`) unter "Admin-Zugangsdaten" einen Benutzernamen und ein Passwort setzen. Sobald ein Passwort gesetzt ist, wird der Adminbereich geschützt.

### Credentials verwalten
- **Im Webinterface**: Unter `/admin` → "Admin-Zugangsdaten" → "Details einblenden"
  - Benutzername anpassen
  - Passwort ändern (leer lassen, um bestehendes zu behalten)
- **Per Datei**: `credentials.json` im Hauptverzeichnis
  ```json
  {
    "admin_username": "admin",
    "admin_password": "dein-sicheres-passwort",
    "secret_key": "generierter-secret-key"
  }
  ```

### Fallback auf Umgebungsvariablen
Falls keine `credentials.json` existiert, werden die Credentials aus Umgebungsvariablen geladen:
- `ADMIN_USERNAME` (default: "admin")
- `ADMIN_PASSWORD`
- `SECRET_KEY`

**Hinweis**: Die Datei `credentials.example.json` enthält eine Vorlage und kann als Ausgangspunkt verwendet werden.

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

## Migration für bestehende Deployments
Wenn du bereits ein Deployment mit Umgebungsvariablen (`ADMIN_USERNAME`, `ADMIN_PASSWORD`) hast:

1. **Option A - Credentials automatisch migrieren:**
   - Starte die Anwendung normal - sie liest die Credentials aus den Umgebungsvariablen
   - Rufe `/admin` auf und logge dich mit den Env-Credentials ein
   - Unter "Admin-Zugangsdaten" kannst du die Credentials in die Datei übernehmen (optional neue Werte setzen)
   - Nach dem Speichern werden die Credentials in `credentials.json` gespeichert

2. **Option B - Manuell migrieren:**
   - Erstelle `credentials.json` im Hauptverzeichnis:
     ```bash
     cat > credentials.json << EOF
     {
       "admin_username": "dein-username",
       "admin_password": "dein-passwort",
       "secret_key": "$(openssl rand -hex 16)"
     }
     EOF
     chmod 600 credentials.json
     ```
   - Optional: Entferne `ADMIN_USERNAME` und `ADMIN_PASSWORD` aus den Umgebungsvariablen

**Hinweis**: Beide Systeme funktionieren parallel - Umgebungsvariablen werden als Fallback verwendet, wenn `credentials.json` nicht existiert.
