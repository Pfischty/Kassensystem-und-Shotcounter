# Troubleshooting

Diese Datei ergänzt das [Betriebshandbuch](Betriebshandbuch.md) um technische Details.
Für normale Bedienprobleme zuerst dort oder im [Event Quickstart](EventQuickstart.md) nachsehen.

Verbindung per SSH aufbauen:
1. Der Raspi hat auf der LAN1 Schnittstelle die Fixe IP: 192.168.50.1
2. Wenn der WLAN accespoint verbunden wird, kann per WLAN die verbindung aufenommen werden. Der Raspi ist DHCP Server
3. Login per SSH mit dem User jubla (hat root rechte) : 
```bash
ssh jubla@192.168.50.1
```
Passwort: 

## Häufige Bedienfehler

Die häufigsten Anwndungs-Fehler sind bereits im Handbuch beschrieben:

- kein aktives Event
- Admin-Login unbekannt
- Kasse oder Shotcounter öffnen nicht
- WLAN-Verbindung schlägt fehl
- Update funktioniert nicht

Direktlink:

- [Zum Betriebshandbuch](Betriebshandbuch.md)
- [Zum Event Quickstart](EventQuickstart.md)

## Admin Credentials

### Im Webinterface verwalten

Pfad:

- `/admin` -> `Admin-Zugangsdaten` -> `Details einblenden`

Möglichkeiten:

- Benutzername ändern
- Passwort ändern
- Passwort leer lassen, um das bestehende Passwort beizubehalten

### Dateibasierter Speicher

Standarddatei:

- `instance/credentials.json`

Beispiel:

```json
{
  "admin_username": "admin",
  "admin_password": "dein-sicheres-passwort",
  "secret_key": "generierter-secret-key"
}
```

### Fallback auf Umgebungsvariablen

Falls keine `instance/credentials.json` existiert, werden Credentials aus Umgebungsvariablen gelesen:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SECRET_KEY`

Zusatz:

- `credentials.example.json` enthält eine Vorlage
- mit `CREDENTIALS_FILE` kann der Speicherort überschrieben werden

## Logs

Anwendungslog:

- `instance/logs/app.log`

Dort stehen unter anderem:

- Admin-Aktionen
- Kassenaktivitäten
- Shotcounter-Aktionen
- Update- und Fehlerhinweise

## Wenn Netzwerkfunktionen im Admin nicht gehen

Prüfen:

1. Läuft die App auf dem vorgesehenen Pi?
2. Existiert `scripts/pi_manage.sh`?
3. Hat der Service genügend Rechte für WLAN oder Updates?

Technische Referenzen:

- [pi_deployment.md](pi_deployment.md)
- [ip_network.md](ip_network.md)

## Wenn System-Update fehlschlägt

Prüfen:

1. Gibt es lokale Änderungen im Git-Repo?
2. Ist das Update-Service korrekt eingerichtet?
3. Darf der Service `systemctl start kassensystem-update.service` ausführen?

Siehe:

- [pi_deployment.md](pi_deployment.md)

## Tests

Wenn lokal `pytest` nicht gefunden wird, zuerst die Entwicklungsabhängigkeiten installieren:

```bash
pip install -r requirements-dev.txt
```

Dann:

```bash
pytest
```

oder:

```bash
make test
```
