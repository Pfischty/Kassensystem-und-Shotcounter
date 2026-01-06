Ziel: Ein Programm entwickeln, das misst, welches Team bei einem Fest die meisten Shots konsumiert hat.

Haupt-App-Pfad
--------------
Der aktive Code liegt unter `Shotcounter/`. Templates, Static-Dateien und die SQLite-Datenbank (`instance/teamliste.db`) werden dort erwartet. Andere Duplikate außerhalb des Ordners sind entfernt bzw. verlinkt.

Start
-----
- Mit Flask-CLI: `flask --app Shotcounter.app --debug run`
- Direkt: `python app.py` (verwendet den Forwarder im Repository-Root)

Routen-Überblick
----------------
- `/registration`: Registrierung neuer Teams (persistiert in der DB)
- `/punkte`: Punkte zu registrierten Teams hinzufügen
- `/leaderboard`: Rangliste der aktuellen Ergebnisse
- `/admin`: Korrekturen (bearbeiten/löschen)
- `/team/delete/<id>` und `/team/update/<id>`: Hilfsrouten für Admin
- `/preisliste`: Preisliste (noch unfertig)
- `/stats`: Kassenstatistik (Umsatz & verkaufte Getränke)

Hinweis zur Live-Aktualisierung
-------------------------------
WebSocket-Events (`socketio.emit('update_leaderboard')`) werden gesendet, damit sich die Rangliste automatisch aktualisieren kann, wenn anderswo Punkte gepostet werden.

Konfiguration & Kasse
---------------------
Die Kasse lädt Buttons/Preise aus `Shotcounter/kassensystem_config.json`. Falls diese Datei fehlt oder ungültig ist, wird automatisch `kassensystem_config.example.json` verwendet. Beim Abschluss einer Bestellung (`Neuer Kunde`) werden Umsatz und Stückzahlen in `instance/teamliste.db` protokolliert; die Kassenstatistik greift auf diese Daten zu.
