# Kassensystem und Shotcounter

Dieses Projekt ist eine gemeinsame Weboberfläche für den Eventbetrieb auf einem Raspberry Pi.
Es kombiniert:

- `Kasse` für Verkauf, Warenkorb, Abschluss und Statistik
- `Shotcounter` für Teamverwaltung, Shot-Erfassung, Touch-Eingabe und Leaderboard
- `Admin` für Eventverwaltung, Produkte, Bilder, Netzwerk, Credentials und Updates

## Schnell einsteigen

Für den echten Einsatz vor Ort ist das neue DAU-Handbuch der primäre Einstieg:

- [DAU-Betriebshandbuch](docs/DAU_Betriebshandbuch.md)

## Dokumentation

- [DAU-Betriebshandbuch](docs/DAU_Betriebshandbuch.md)
  Schritt-für-Schritt-Anleitung für Aufbau, Erstinbetriebnahme und Betrieb am Event
- [Initial Setup](docs/InitialSetup.md)
  Technischer Schnellzugang für lokale Entwicklung und Pi-Grundsetup
- [Troubleshooting](docs/Troubleshooting.md)
  Fehlerbilder, Notfälle und technische Hinweise
- [Raspberry Pi Deployment](docs/pi_deployment.md)
  Technische Service-, Update-, Backup- und Kiosk-Einrichtung
- [Netzwerkarchitektur](docs/ip_network.md)
  LAN-, DHCP-, DNS- und Gateway-Konzept für den Raspberry Pi

## Wichtige Oberflächen

- `/` Übersicht
- `/admin` Adminbereich
- `/cashier` Kasse
- `/shotcounter` Shotcounter
- `/shotcounter/touch` Touch-Eingabe
- `/shotcounter/leaderboard` Vollbild-Leaderboard
- `/preisliste` Preisliste

## Hinweise

- Beim ersten Start ist der Adminbereich ohne Passwort erreichbar, bis unter `Admin-Zugangsdaten` ein Passwort gesetzt wird.
- Ohne aktives Event zeigen `Kasse`, `Shotcounter` und `Preisliste` absichtlich einen Hinweis oder `404`, damit kein falsches Event bedient wird.
- Für den produktiven Pi-Betrieb sind die Dateien unter `docs/` maßgeblich, nicht nur dieses README.
