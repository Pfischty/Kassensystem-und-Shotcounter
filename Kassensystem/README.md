# Kassensystem

Dieses Kassensystem ist als schlanke Flask‑App umgesetzt. Preise und Buttons werden jetzt vollständig über eine JSON‑Datei gesteuert, sodass es keine konkurrierenden Preislisten mehr gibt.

## Starten

1. Abhängigkeiten installieren (z. B. in einem virtuellen Environment):
   ```bash
   pip install flask flask_sqlalchemy sqlalchemy
   ```
2. App starten:
   ```bash
   python Kassensystem/app.py
   ```
   Die Anwendung lauscht standardmäßig auf `http://0.0.0.0:5000` und legt Bestellungen in `orders.db` (SQLite) im gleichen Ordner ab.

## Konfiguration

1. Kopiere die Beispielkonfiguration:
   ```bash
   cp Kassensystem/kassensystem_config.example.json Kassensystem/kassensystem_config.json
   ```
2. Passe die Datei an. Jede Schaltfläche besteht aus:
   - `name`: interner Name, wird im Backend gespeichert.
   - `label`: Beschriftung auf dem Button.
   - `price`: Preis in CHF (negative Werte z. B. für Depot‑Rückgaben).
   - `css_class`: bestimmt die Buttonfarbe. Vordefiniert sind `suess`, `bier`, `wein`, `flasche`, `gross`, `depot`, `Weinglassdepot`, `kaffee`, `shot`, `clear`.

Bei fehlender oder ungültiger `kassensystem_config.json` greift die App automatisch auf die mitgelieferte `kassensystem_config.example.json` zurück.
