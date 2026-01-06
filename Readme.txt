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

Konfiguration:
- Lege eine `.env`-Datei (siehe `.env.example`) mit mindestens `SECRET_KEY`, `DATABASE_URI`, `ADMIN_USERNAME` und `ADMIN_PASSWORD` an. Alle sensible Einstellungen werden zur Laufzeit über diese Umgebungsvariablen geladen.
- `/admin`, `/manage` sowie alle `/team/*`-Routen sind per HTTP Basic Auth geschützt. Verwende die oben genannten Credentials oder passe sie in der `.env` an.
- CSRF-Schutz ist für alle Formular-POSTs aktiv (Flask-WTF). Jede Formularvorlage enthält bereits das Token.
- Setze `APP_ENV=production`, um Debug-Mode abzuschalten und den eingebauten Development-Server nicht zu nutzen. Im Development-Mode kann per `python app.py` mit `socketio.run` gestartet werden (Standard: Host `0.0.0.0`, Port `5000`).
