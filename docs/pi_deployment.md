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
3. Virtuelle Umgebung anlegen und Abhängigkeiten installieren (online oder offline):
   ```bash
   ./scripts/pi_manage.sh create-venv
   ./scripts/pi_manage.sh install-deps            # online
   ./scripts/pi_manage.sh install-deps --offline  # nutzt ./wheels
   ```

## Dienst einrichten (Autostart & Robustheit)
1. Systemd-Unit schreiben (Port anpassbar, Standard 8000):
   ```bash
   sudo ./scripts/pi_manage.sh write-service --port 8000
   ```
   Dabei wird automatisch `/etc/kassensystem.env` mit einem SECRET_KEY erstellt. Passe die Datei bei Bedarf an.
2. Dienst aktivieren und starten:
   ```bash
   sudo ./scripts/pi_manage.sh enable-service
   ```
3. Status prüfen:
   ```bash
   sudo ./scripts/pi_manage.sh status
   ```

Der Dienst startet nach Stromausfall/Neustart automatisch und nutzt die rotierenden Logs unter `instance/logs/app.log` (Standard des Projekts).

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
