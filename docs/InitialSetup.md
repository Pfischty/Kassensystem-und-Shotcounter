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

## NFC-Kartenleser lokal testen (ACR122U)

Funktioniert auch ohne Pi, direkt auf dem Dev-Rechner — Voraussetzung ist nur
ein per USB angeschlossener ACR122U. Unter macOS ist PC/SC bereits im System
eingebaut (kein `pcscd` nötig); unter Linux siehe
[pi_deployment.md](pi_deployment.md#nfc-kartenleser-acr122u-für-den-shotcounter).

1. App starten, z. B. mit `flask --app app run --debug`
   — läuft dann auf `http://127.0.0.1:5000`.
2. Event anlegen und aktivieren: `/admin` → Event erstellen (Shotcounter
   aktiviert lassen) → aktivieren.
3. NFC-Bridge starten — **kein zweites Terminal nötig**: `/shotcounter/nfc`
   öffnen und im Kasten "NFC-Bridge-Prozess" auf "Bridge starten" klicken.
   Das startet `nfc_bridge.py` im Hintergrund und zeigt ihm automatisch den
   richtigen Host/Port (den der Browser gerade benutzt) — ganz ohne
   `NFC_BASE_URL` von Hand zu setzen. Funktioniert plattformunabhängig
   (macOS/Linux/Windows), da die Prozesssteuerung über `psutil` läuft statt
   über systemd. Der Punkt daneben wird grün, sobald die Bridge läuft;
   Logs landen wie im Pi-Betrieb unter `instance/logs/nfc_bridge.log`.
   *(Alternativ weiterhin manuell möglich: `export NFC_BASE_URL=http://127.0.0.1:5000`
   und `python3 nfc_bridge.py` in einem zweiten Terminal — z. B. für
   automatisierte Tests ohne Browser.)*
4. Karte programmieren: im selben `/shotcounter/nfc`, Team wählen oder
   neuen Namen eingeben, auf "Karte anlernen" klicken, Karte auf den Leser
   legen. Die Bindung erscheint danach in der Liste.
5. Live-Popup testen: `/shotcounter/touch` öffnen, dieselbe Karte erneut
   auflegen (kurz abheben und neu auflegen, falls sie schon länger als ein
   paar Sekunden auf dem Leser lag) — das Popup mit Teamname erscheint,
   Shot-Anzahl eingeben, "Shots buchen" bestätigen.

Damit lässt sich der komplette Ablauf (Anlernen → Live-Scan → Shots buchen)
ohne Pi und ohne systemd-Dienst durchspielen — der "Bridge starten"-Button
ist ausdrücklich für genau diesen lokalen Testfall gedacht; im Dauerbetrieb
auf dem Pi bleibt der systemd-Dienst (`pi_manage.sh write-nfc`) die
empfohlene Lösung, da er unabhängig vom Browser läuft und bei einem Absturz
automatisch neu startet.

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
