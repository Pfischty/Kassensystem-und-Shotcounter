Ziel:
Ein Programm entwickeln, das misst, welches Team bei einem Fest die meisten Shots konsumiert hat.

Erklärung:
- /registration: Ermöglicht die Registrierung neuer Teams und sichert diese in der Datenbank.
- /punkte: Auf dieser Seite können Punkte zu bereits registrierten Teams hinzugefügt werden (CSS-Datei erstellt mit ChatGPT).
- /leaderboard: Zeigt eine Rangliste der aktuellen Ergebnisse an (CSS-Datei erstellt mit ChatGPT).
- /admin: Ermöglicht die Korrektur von Fehlern.
- /team/delete/<id> und /team/update/<id>: Übernommen aus den Übungsaufgaben.
- /preisliste: Zeigt eine Preisliste an, die jedoch noch nicht fertiggestellt ist.

Frage:
Gibt es eine Möglichkeit, eine geöffnete Seite zu aktualisieren, wenn auf einer anderen Seite etwas gepostet wird?
Das Ziel ist es, dass die Rangliste durchgehend auf einem Bildschirm angezeigt wird, während in einem anderen Tab auf einem anderen Bildschirm Punkte hinzugefügt werden.
Eine automatische Aktualisierung der Rangliste wäre ideal, da die aktuelle Lösung – das Aktualisieren der Rangliste alle 10 Sekunden – nicht sehr effizient ist.

Konfiguration & Migrationen:
- Die Anwendung nutzt nun Flask-Migrate. Installiere die Abhängigkeiten (siehe requirements.txt) und setze die gewünschte Umgebung über `FLASK_ENV` (development/testing/production).
- DB-URIs pro Umgebung:
  - Development: `DEV_DATABASE_URI` (Standard: sqlite:///dev.db)
  - Testing: `TEST_DATABASE_URI` (Standard: sqlite:///test.db)
  - Production: `DATABASE_URI` (Standard: sqlite:///prod.db)
- Beispiel: `FLASK_ENV=production DATABASE_URI=postgresql://user:pass@host/dbname flask --app Kassensystem.app db upgrade`

Backup- & Reset-Workflow (Beispiele mit SQLite):
1. Backup ziehen: `cp dev.db dev-backup-$(date +%Y%m%d%H%M%S).db`
2. Aktuellen Stand anzeigen: `flask --app Kassensystem.app db current`
3. Auf neuesten Stand migrieren: `flask --app Kassensystem.app db upgrade`
4. Einen Schritt zurückrollen: `flask --app Kassensystem.app db downgrade -1`
5. Reset (z. B. für Tests): `rm dev.db && flask --app Kassensystem.app db upgrade`
