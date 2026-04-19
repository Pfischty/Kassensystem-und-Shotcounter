# Initial Setup

Diese Datei ist die technische Ergänzung zum [Betriebshandbuch](Betriebshandbuch.md).
Wenn du das System nur bedienen willst, beginne dort oder im [Event Quickstart](EventQuickstart.md).

## Für wen ist diese Datei?

Für Personen, die:

- die Anwendung lokal entwickeln
- den Raspberry Pi technisch vorbereiten
- Services, Abhängigkeiten oder das Deployment einrichten

## Lokales Entwicklungs-Setup

1. Virtuelle Umgebung anlegen:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

Für Entwicklung und Tests zusätzlich:

```bash
pip install -r requirements-dev.txt
```

3. Datenbank initialisieren:

```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

4. Entwicklung starten:

```bash
flask --app app run --debug
```

Zugriff aus dem LAN:

```bash
flask --app app run --host 0.0.0.0 --port 8000
```

Alternativ:

```bash
make run
```

## Raspberry-Pi-Grundsetup

Für den produktiven Betrieb ist die technische Hauptreferenz:

- [pi_deployment.md](pi_deployment.md)

Kurzüberblick:

1. Projekt auf den Pi kopieren oder klonen
2. `.venv` anlegen
3. Abhängigkeiten installieren
4. Service schreiben und aktivieren
5. Optional Backups und Kiosk-Modus aktivieren

## Zugangsdaten

Beim ersten Start ist der Adminbereich offen, bis ein Passwort gesetzt wird.

Sobald ein Passwort benötigt wird, gelten die technischen Details in:

- [Troubleshooting.md](Troubleshooting.md)

## Hinweis zur Bedienung

Die fachliche Schritt-für-Schritt-Bedienung liegt bewusst nicht in dieser Datei, sondern im:

- [Betriebshandbuch](Betriebshandbuch.md)
