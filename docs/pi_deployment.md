# Raspberry Pi Deployment & Wartung

Dieses Projekt kann auf einem Raspberry Pi im Offline-LAN (Ethernet) betrieben werden, während für Updates optional WLAN genutzt wird. Das Skript `scripts/pi_manage.sh` bündelt die wichtigsten Schritte.

## Vorbereitung (einmalig)
1. Repository nach `/opt/kassensystem-und-shotcounter` klonen (oder an Wunschpfad).
2. (Optional) Offline-Wheels vorbereiten, solange Internet vorhanden ist:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip download -r requirements.txt -d wheels/
   ```
   Für Entwicklung/Tests:
   ```bash
   pip download -r requirements-dev.txt -d wheels/
   ```
3. Virtuelle Umgebung anlegen und Abhängigkeiten installieren (online oder offline):
   ```bash
   ./scripts/pi_manage.sh create-venv
   ./scripts/pi_manage.sh install-deps            # online
   ./scripts/pi_manage.sh install-deps --offline  # nutzt ./wheels
   ```
   Für Entwicklung/Tests:
   ```bash
   ./scripts/pi_manage.sh install-deps --dev
   ```

## Dienst einrichten (Autostart & Robustheit)
1. Systemd-Unit schreiben (Port anpassbar, Standard 8000):
   ```bash
   sudo ./scripts/pi_manage.sh write-service --port 8000
   ```
   Dabei wird automatisch `/etc/kassensystem.env` mit `SECRET_KEY`, Admin-Zugang und Backup-Parametern erstellt. Passe die Datei bei Bedarf an.
   Der Dienst läuft als dedizierter System-User `kassensystem` und ist mit basic Hardening-Optionen abgesichert. Wenn das Repo unter `/home` oder `/root` liegt, deaktiviert das Skript `ProtectHome`, damit der Dienst auf das Projekt zugreifen kann.
2. Dienst aktivieren und starten:
   ```bash
   sudo ./scripts/pi_manage.sh enable-service
   ```
3. Status prüfen:
   ```bash
   sudo ./scripts/pi_manage.sh status
   ```

Der Dienst startet nach Stromausfall/Neustart automatisch und nutzt die rotierenden Logs unter `instance/logs/app.log`.

## Admin-Zugang
Sobald `ADMIN_PASSWORD` gesetzt ist (Standard im `/etc/kassensystem.env`), sind alle `/admin`-Routen per Basic Auth geschützt.

## Datenbank-Backups (täglich)
```bash
sudo ./scripts/pi_manage.sh write-backup
sudo ./scripts/pi_manage.sh enable-backup
```
Die Backups landen in `BACKUP_DIR` (Standard `instance/backups` im Repo), die Aufbewahrung wird über `BACKUP_RETENTION` (Tage) gesteuert.

## Kiosk-Modus (Touchscreen)
1. URL optional setzen (z. B. `http://localhost:8000/shotcounter/touch`) in `/etc/kassensystem.env`:
   ```bash
   KIOSK_URL=http://localhost:8000/cashier
   ```
2. Service schreiben und aktivieren:
   ```bash
   sudo ./scripts/pi_manage.sh write-kiosk
   sudo ./scripts/pi_manage.sh enable-kiosk
   ```
Voraussetzung: `chromium` oder `chromium-browser` ist installiert.

## NFC-Kartenleser (ACR122U) für den Shotcounter
Der Shotcounter kann Shot-Teams über NFC/RFID-Karten (getestet mit dem ACS ACR122U)
erkennen: Karten werden im Adminbereich `/shotcounter/nfc` einem Team zugeordnet
("anlernen") und lösen im Festbetrieb auf `/shotcounter/touch` automatisch ein
Popup zum Buchen der Shot-Anzahl aus.

Der Kartenleser wird von einem eigenständigen Hintergrundprozess (`nfc_bridge.py`)
angesprochen, nicht von der Web-App selbst — so funktioniert das Auslesen
unabhängig davon, mit wie vielen Gunicorn-Workern die App läuft, und ein
Reader-Hänger reißt nicht die ganze Kasse mit.

1. PC/SC-Unterstützung installieren (einmalig, benötigt Internet):
   ```bash
   sudo apt install pcscd libpcsclite1 libpcsclite-dev swig
   sudo systemctl enable --now pcscd
   ```
   (`swig` und die `libpcsclite`-Header werden gebraucht, weil `pyscard` auf dem Pi
   aus dem Quellcode gebaut wird — dafür gibt es i. d. R. kein fertiges ARM-Wheel.)
2. ACR122U per USB anschließen und testen (`lsusb` sollte `072f:2200 Advanced Card Systems, Ltd ACR122U` zeigen).
3. `pyscard` ist Teil von `requirements.txt` und wird durch `install-deps` mitinstalliert.
4. Bridge-Dienst schreiben und aktivieren:
   ```bash
   sudo ./scripts/pi_manage.sh write-nfc
   sudo ./scripts/pi_manage.sh enable-nfc
   ```
5. Status/Logs prüfen:
   ```bash
   sudo systemctl status kassensystem-nfc
   tail -f instance/logs/nfc_bridge.log
   ```

Auf der Seite `/shotcounter/nfc` zeigt ein grüner Punkt, ob die Bridge aktuell
mit der App kommuniziert (Heartbeat). Die Kommunikation zwischen Bridge und
App läuft ausschließlich über `localhost` und ist über ein beim ersten Start
automatisch erzeugtes Secret (`instance/nfc_secret.txt`) abgesichert.

Es wird nur die UID der Karte gespeichert (kein Beschreiben des Kartenspeichers) —
das funktioniert mit praktisch jedem NFC-Wristband/jeder Karte und kommt ohne
Mifare-Schlüsselverwaltung aus.

### Geräteerkennung auf mehreren Instanzen
Der Leser wird nicht über einen festen USB-Pfad angesprochen, sondern über
PC/SC autoerkannt (`smartcard.System.readers()` fragt bei jedem Zyklus den
laufenden `pcscd`/PC/SC-Dienst ab). Das bedeutet:
- Auf jedem Pi (und auch lokal auf einem Dev-Rechner) wird der ACR122U ohne
  Konfiguration gefunden, unabhängig davon, an welchem USB-Port er hängt.
- Wird er während des Betriebs abgezogen/wieder angesteckt, erkennt die
  Bridge das automatisch beim nächsten Zyklus (kein Neustart nötig).
- Sind mehrere PC/SC-Leser an derselben Instanz angeschlossen, wählt die
  Bridge den, dessen Name zu `NFC_READER_NAME_FILTER` passt (Standard:
  `ACR122`, Groß-/Kleinschreibung egal). Passt keiner, wird der erste
  gefundene Leser genutzt und eine Warnung geloggt — so bleibt die Auswahl
  transparent statt "zufällig" zu wirken.
- Der gewählte Lesername wird beim Start bzw. bei einem Wechsel einmalig
  geloggt (`instance/logs/nfc_bridge.log`, Zeile "Verwende Leser: ...").

### Fehlerbehandlung der Bridge
- **Kein Leser gefunden**: Warnung im Log, Heartbeat meldet den Fehlerstatus
  an die App (sichtbar als roter Punkt auf `/shotcounter/nfc`), die Bridge
  läuft weiter und prüft alle 2s erneut.
- **PC/SC-Dienst nicht erreichbar** (`pcscd` läuft nicht): eigene, klare
  Fehlermeldung im Log statt eines rohen Tracebacks; Bridge bleibt am Leben
  und versucht es weiter.
- **Karte während des Lesens entfernt / Leser exklusiv belegt**: wird
  abgefangen, führt nur zu einer Debounce-Zurücksetzung, nicht zum Absturz.
- **Web-App gerade nicht erreichbar** (Neustart, Deploy): Scan-/Heartbeat-
  Meldungen schlagen fehl, werden geloggt und beim nächsten Zyklus erneut
  versucht; keine Warteschlange, kein Datenverlust bei kurzen Ausfällen (der
  nächste Kartenscan wird ganz normal wieder gemeldet).
- Jeder unerwartete Fehler in der Leseschleife wird abgefangen, geloggt und
  als Heartbeat-Fehlermeldung an die App weitergereicht, statt den ganzen
  Prozess (und damit den Festbetrieb) zu beenden.

## Updates einspielen
- Online (z. B. temporär über WLAN mit Internetzugang):
  ```bash
  sudo ./scripts/pi_manage.sh update --branch main
  ```
- Offline (nur lokale Änderungen, keine Git-Abfrage – nutzt vorbereitete Wheels):
  ```bash
  sudo ./scripts/pi_manage.sh update --offline
  ```

  Der Befehl installiert Abhängigkeiten, schreibt keine Git-Daten wenn `--offline` gesetzt ist, und startet den Dienst neu.

## WLAN-Helfer (optional für Wartung)
- Netzwerk hinzufügen und direkt re-konfigurieren:
  ```bash
  sudo ./scripts/pi_manage.sh wifi-add "<SSID>" "<Passwort>"
  ```
  Das ergänzt `/etc/wpa_supplicant/wpa_supplicant.conf` und stößt ein `wpa_cli reconfigure` an.
- WLAN-Schnittstelle aktivieren/deaktivieren:
  ```bash
  sudo ./scripts/pi_manage.sh wifi-up
  sudo ./scripts/pi_manage.sh wifi-down
  ```

> Hinweis: Die WLAN-Helfer erwarten ein klassisches Raspberry-Pi-Setup mit `wpa_supplicant` und Interface `wlan0`. In restriktiven Umgebungen kannst du die Befehle anpassen (z. B. für `NetworkManager`). Für Sicherheit empfiehlt es sich, WLAN nur während Wartungsfenstern zu aktivieren und Zugriffe zu beschränken (Firewall/SSH).
