# Betriebshandbuch

Dieses Handbuch ist für Helferinnen, Helfer und verantwortliche Personen gedacht, die das System während eines Events bedienen. Es beschreibt den normalen Betrieb über die Weboberfläche und vermeidet bewusst technische Details für Terminal, Deployment oder Service-Konfiguration.

Die technische Ergänzung dazu steht in:

- [Event Quickstart](EventQuickstart.md)
- [Initial Setup](InitialSetup.md)
- [Troubleshooting](Troubleshooting.md)
- [Raspberry Pi Deployment](pi_deployment.md)
- [Netzwerkarchitektur](ip_network.md)

## 1. Zweck des Systems

Das System steuert einen Eventbetrieb mit einem Raspberry Pi als Zentrale. Je nach Event können folgende Bereiche genutzt werden:

- `Übersicht`: zeigt, ob ein Event aktiv ist, und bietet Schnellzugriff auf die wichtigsten Seiten
- `Admin`: für Events, Produkte, Bilder, Zugangsdaten, Netzwerk und Updates
- `Kasse`: für Verkäufe und Bestellabschlüsse
- `Shotcounter`: für Teams und Shots
- `Shotcounter Touch`: vereinfachte Touch-Oberfläche zum schnellen Buchen
- `Shotcounter Vollbild`: Anzeige für externen Bildschirm oder TV
- `Preisliste`: Anzeige für Preise auf einem zweiten Bildschirm

## 2. Rollen und Aufgaben

Nicht jede Person soll alles bedienen. Im Eventbetrieb gilt diese einfache Rollenverteilung:

- `Kassenpersonal`: arbeitet nur in `Kasse`
- `Shotcounter-Team`: arbeitet in `Shotcounter` oder `Shotcounter Touch`
- `Verantwortliche Person`: darf `Admin`, Event-Einstellungen, Exporte, Bilder, Netzwerk und Updates bedienen

Wenn unklar ist, ob eine Änderung während des Events sicher ist, nicht raten, sondern die verantwortliche Person holen.

## 3. Schnellstart vor Eventbeginn

Wenn es schnell gehen muss, zuerst nur diese Schritte durchgehen:

1. Raspberry Pi einschalten und mit dem Event-Switch verbinden.
2. Warten, bis das System vollständig gestartet ist.
3. Tablet oder Laptop ebenfalls mit demselben Netz verbinden.
4. Im Browser `http://kasse:8000` öffnen.
5. Falls die Seite nicht lädt, `http://kasse.lan:8000` testen.
6. Falls auch das nicht funktioniert, `http://192.168.50.1:8000` verwenden.
7. Prüfen, ob ein aktives Event vorhanden ist.
8. Danach nur die benötigte Seite verwenden: `Kasse`, `Shotcounter` oder `Shotcounter Touch`.

Wenn die Startseite `Kein aktives Event` zeigt, ist das kein Systemfehler. Es muss zuerst im Adminbereich ein Event aktiviert werden.

## 4. Geräte und Netzwerk

Im typischen Eventbetrieb gehören dazu:

- Raspberry Pi als Zentrale
- Netzwerkswitch
- optional ein WLAN-Access-Point für Wartung oder definierte Geräte
- ein oder mehrere Tablets, Laptops oder Kassen-Geräte
- optional ein externer Bildschirm für Leaderboard oder Preisliste
- optional weitere LAN-Geräte wie Drucker

Wichtig:

- Alle Geräte für den Eventbetrieb müssen im selben Netz hängen.
- Für den normalen Betrieb ist kabelgebundenes LAN robuster als WLAN.
- WLAN nur nutzen, wenn es für Wartung, Updates oder bestimmte Endgeräte wirklich gebraucht wird.

## 5. Welche Adresse wird geöffnet?

Standard für die Dokumentation und den Betrieb ist immer:

- `http://kasse:8000`

Falls die Namensauflösung nicht funktioniert:

- `http://kasse.lan:8000`
- `http://192.168.50.1:8000`

Wenn direkt am Raspberry Pi gearbeitet wird:

- `http://localhost:8000`

Erwartetes Ergebnis:

- Die Startseite oder Übersicht wird geladen.
- Wenn noch kein Event aktiv ist, erscheint ein entsprechender Hinweis.

## 6. Vorbereitung vor dem Event

### 6.1 Raspberry Pi einschalten

1. Raspberry Pi mit Strom verbinden.
2. Warten, bis das System vollständig gestartet ist.
3. Falls ein Bildschirm angeschlossen ist, prüfen, ob Desktop oder Browser sichtbar sind.

Erwartetes Ergebnis:

- Das System ist gestartet und über das Netz erreichbar.

### 6.2 Netzwerk aufbauen

1. Raspberry Pi mit `eth0` an den Event-Switch anschließen.
2. Tablets, Kassen-Laptops und weitere Event-Geräte an denselben Switch anschließen.
3. Falls ein externer Bildschirm benutzt wird, das Anzeigegerät wie geplant anschließen.

Erwartetes Ergebnis:

- Alle für den Betrieb benötigten Geräte befinden sich im gleichen Netz.

### 6.3 Browsertest

1. Auf einem Gerät im Event-Netz den Browser öffnen.
2. `http://kasse:8000` eingeben.
3. Falls nötig auf `http://kasse.lan:8000` oder `http://192.168.50.1:8000` ausweichen.

Erwartetes Ergebnis:

- Die Weboberfläche lädt.

Wenn es nicht klappt:

- zur [Notfallseite](#13-notfallseite) springen

## 7. Erster Admin-Zugang

### 7.1 Admin öffnen

1. In der Navigation `Admin` wählen.
2. Falls noch kein Passwort gesetzt ist, öffnet sich der Adminbereich direkt.
3. Falls Benutzername und Passwort abgefragt werden, die aktuell gültigen Zugangsdaten verwenden.

Wichtig:

- Keine Zugangsdaten in der Doku notieren.
- Zugangsdaten nur an verantwortliche Personen weitergeben.

### 7.2 Zugangsdaten ändern

1. Im Adminbereich `Admin-Zugangsdaten` öffnen.
2. Benutzernamen bei Bedarf anpassen.
3. Neues Passwort setzen.
4. `Zugangsdaten speichern` wählen.

Erwartetes Ergebnis:

- Der Adminbereich ist geschützt.
- Wenn das Passwort-Feld leer bleibt, wird ein bestehendes Passwort nicht geändert.

## 8. Event anlegen und aktivieren

### 8.1 Neues Event erstellen

1. Im Adminbereich `+ Neues Event` klicken.
2. Eventnamen eintragen.
3. `Kassensystem aktiv` aktiviert lassen, wenn verkauft werden soll.
4. `Shotcounter aktiv` aktiviert lassen, wenn Teams und Shots geführt werden sollen.
5. `Auto-Reload beim Hinzufügen (Kasse)` nach Bedarf setzen.
6. `Event anlegen` klicken.

Empfehlung:

- aktiviert lassen, wenn nur wenige Geräte gleichzeitig arbeiten
- deaktivieren, wenn die Kasse möglichst direkt reagieren soll

### 8.2 Event aktivieren

1. Im Bereich `Events` das gewünschte Event suchen.
2. Den Status-Button `Inaktiv - Aktivieren` wählen.

Erwartetes Ergebnis:

- Das Event ist als `aktiv` markiert.
- `Kasse`, `Shotcounter` und `Preisliste` können verwendet werden.

## 9. Event konfigurieren

Die Schaltfläche `Einstellungen` öffnet die Konfiguration des ausgewählten Events. Die Bereiche sind in Tabs unterteilt.

### 9.1 Tab `Allgemein`

Hier werden Grundfunktionen des Events gesteuert.

Wichtige Punkte:

- `Kassensystem aktiv`
- `Shotcounter aktiv`
- `Auto-Reload beim Hinzufügen (Kasse)`
- `Einstellungen aus Event kopieren`

Typischer Ablauf:

1. Haken und Grundoptionen prüfen.
2. Falls ein früheres Event als Vorlage dienen soll, dieses auswählen.
3. `Übernehmen` klicken.
4. Danach `Speichern` klicken.

### 9.2 Tab `Shotcounter`

Hier wird die Darstellung für Touch und Vollbild eingerichtet.

Wichtige Felder:

- `Hintergrund`
- `Primärfarbe (Karten)`
- `Schriftgröße Titel`
- `Schriftgröße Teams`
- `Teams im Leaderboard`
- `Leaderboard Layout`
- `Hintergrundbild auswählen`

Typischer Ablauf:

1. Farben und Größen festlegen.
2. Anzahl sichtbarer Teams bestimmen.
3. Optional ein Bild aus der Bilderverwaltung wählen.
4. `Speichern` klicken.

### 9.3 Tab `Preisliste`

Hier wird die Anzeige für einen Bildschirm oder TV konfiguriert.

Wichtige Felder:

- `Schriftgröße`
- `Wechsel-Intervall (Sek.)`
- `Hintergrundfarbe`
- `Hintergrundbild auswählen`

Typischer Ablauf:

1. Anzeigegröße und Intervall festlegen.
2. Optional Hintergrundbild wählen.
3. Produkte und Kategorien für die Anzeige ein- oder ausblenden.
4. Reihenfolge anpassen.
5. `Speichern` klicken.

### 9.4 Tab `Kasse`

Hier wird gesteuert, was in der Kassenansicht sichtbar ist.

Typischer Ablauf:

1. Produkte prüfen.
2. Kategorien hinzufügen oder umsortieren.
3. Sichtbarkeit setzen.
4. `Speichern` klicken.

### 9.5 Tab `Alle Produkte & Kategorien`

Das ist die wichtigste Stelle für die Produktpflege.

Hier können unter anderem:

- Produkte hinzugefügt werden
- Kategorien angelegt werden
- Preise geändert werden
- Farben angepasst werden
- Depot aktiviert werden
- Reihenfolgen per Ziehen geändert werden

Typischer Ablauf:

1. `+ Produkt` klicken.
2. Produktname, Label, Preis und Kategorie eintragen.
3. Farbe für die Kachel setzen.
4. Bei Bedarf `Depot` aktivieren.
5. Produkte sortieren.
6. `Speichern` klicken.

### 9.6 Tab `Import/Export`

Hier können Einstellungen und Produkte als JSON gespeichert oder geladen werden.

Sinnvolle Einsatzzwecke:

- Wiederverwendung zwischen Events
- Sicherung von Konfigurationen
- Übernahme auf ein anderes Gerät

Wichtig:

- `Produkte-JSON importieren` ersetzt die Produktliste des aktuellen Events.
- `Event-JSON importieren` ersetzt die Einstellungen des aktuellen Events.
- Import nur durch verantwortliche Personen ausführen.

## 10. Bilderverwaltung

Die `Bilderverwaltung` liegt im Adminbereich.

### 10.1 Bild hochladen

1. Unter `Neues Bild hochladen` die Datei auswählen.
2. `Hochladen` klicken.

Erlaubte Formate:

- PNG
- JPG
- GIF
- WebP

### 10.2 Bild umbenennen

1. Beim gewünschten Bild den neuen Namen eintragen.
2. `Umbenennen` klicken.

### 10.3 Bild einem Event zuordnen

1. Zu den Event-Einstellungen zurückgehen.
2. Im Tab `Shotcounter` oder `Preisliste` das Bild auswählen.
3. `Speichern` klicken.

### 10.4 Bild löschen

1. Beim Bild `Löschen` wählen.
2. Warnhinweis bestätigen.

Wichtig:

- Das Bild wird aus Event-Verknüpfungen entfernt.
- Danach müssen betroffene Events ein anderes Bild zugewiesen bekommen.
- Bilder während des laufenden Events nur mit Rücksprache löschen.

## 11. Betrieb während des Events

### 11.1 Kasse bedienen

Seite: `/cashier`

Typischer Ablauf:

1. `Kasse` öffnen.
2. Produkte über die Kacheln hinzufügen.
3. In der `Bestellliste` prüfen, ob alles stimmt.
4. Falls nötig `Letzter Artikel löschen`.
5. `Bestellung abschließen` klicken.

Erwartetes Ergebnis:

- Die Bestellung ist gespeichert.
- Der Warenkorb ist wieder leer.
- Umsatz und Statistiken werden aktualisiert.

### 11.2 Kassenstatistik prüfen

Seite: `/cashier/stats`

Hier sieht man zum Beispiel:

- Umsatz
- Anzahl Bestellungen
- verkaufte Produkte

### 11.3 Shotcounter bedienen

Seite: `/shotcounter`

Typischer Ablauf:

1. Unter `Team hinzufügen` einen Namen eintragen.
2. `Anlegen` klicken.
3. Shots in der Tabelle setzen oder mit `+ Shots` erhöhen.
4. Falls nötig Teamnamen korrigieren oder Team löschen.

### 11.4 Shotcounter Touch benutzen

Seite: `/shotcounter/touch`

Diese Ansicht ist für Touchscreens und schnelles Buchen gedacht.

Typischer Ablauf:

1. Team auswählen.
2. Shot-Anzahl über den Nummernblock eingeben.
3. `Shots buchen` klicken.

Zusätzlich:

- `Neues Team` öffnet direkt ein Eingabefenster.
- `Zur Hauptansicht` führt zur normalen Shotcounter-Ansicht zurück.

### 11.5 Leaderboard anzeigen

Seite: `/shotcounter/leaderboard`

Typischer Ablauf:

1. Shotcounter oder Navigation öffnen.
2. `Leaderboard anzeigen` oder `Shotcounter Vollbild` wählen.
3. Die Seite auf dem externen Bildschirm im Vollbildmodus anzeigen.

### 11.6 Preisliste anzeigen

Seite: `/preisliste`

Typischer Ablauf:

1. `Preisliste` öffnen.
2. Auf dem gewünschten Bildschirm anzeigen.
3. Kategorien wechseln automatisch nach dem eingestellten Intervall.

## 12. Eventabschluss

### 12.1 Eventdetails öffnen

1. In `Übersicht` oder Admin das Event wählen.
2. `Details` oder die Statistik- und Log-Ansicht öffnen.

### 12.2 CSV-Exporte herunterladen

Auf der Event-Detailseite stehen je nach Funktion unter anderem:

- `Abschlüsse / Bestell-Log`
- `Verkaufte Getränke`
- `Shot-Log`

Diese Dateien eignen sich für:

- Abrechnung
- Nachkontrolle
- Archiv

### 12.3 Event archivieren

1. Im Adminbereich das Event suchen.
2. Den Status-Button `Aktiv - Archivieren` klicken.

Erwartetes Ergebnis:

- Das Event ist nicht mehr aktiv.
- Kasse und Shotcounter sind für dieses Event beendet.

Wichtig:

- Ein aktives Event nur archivieren, wenn wirklich nicht mehr verkauft oder gezählt wird.

### 12.4 Neues Event aus Vorlage erstellen

1. `+ Neues Event` wählen.
2. Im Feld `Vorlage kopieren` ein altes Event wählen.
3. `Übernehmen` klicken.
4. Event anlegen.
5. Aktivieren.

## 13. Notfallseite

### 13.1 Wenn gar nichts mehr klar ist

Diese Reihenfolge immer zuerst prüfen:

1. Lädt `http://kasse:8000`?
2. Falls nein: lädt `http://kasse.lan:8000`?
3. Falls nein: lädt `http://192.168.50.1:8000`?
4. Gibt es ein aktives Event?
5. Ist die richtige Seite geöffnet: `Admin`, `Kasse`, `Shotcounter` oder `Shotcounter Touch`?

### 13.2 Häufige Probleme

#### `Kein aktives Event vorhanden`

Bedeutung:

- Es ist noch kein Event aktiviert.
- Oder das aktive Event wurde archiviert.

Lösung:

1. `Admin` öffnen.
2. Event suchen.
3. `Inaktiv - Aktivieren` klicken.

#### Admin fragt nach Login

Bedeutung:

- Für den Adminbereich wurde ein Passwort gesetzt.

Lösung:

1. Gültige Zugangsdaten eingeben.
2. Falls unbekannt, verantwortliche Person kontaktieren.

#### Kasse, Shotcounter oder Preisliste öffnen nicht

Bedeutung:

- Meistens ist kein aktives Event vorhanden.
- Oder die Funktion wurde im Event deaktiviert.

Lösung:

1. `Admin` öffnen.
2. Event-Einstellungen prüfen.
3. Im Tab `Allgemein` die Haken kontrollieren.
4. Event aktivieren oder Einstellung korrigieren.

#### WLAN verbindet nicht

Lösung:

1. Im Adminbereich `Netzwerkeinstellungen` öffnen.
2. WLAN scannen.
3. Richtiges Netz wählen.
4. Passwort exakt eingeben.
5. Erneut versuchen.

Wenn das nicht hilft:

- Eventbetrieb über LAN weiterführen
- Updates später mit technischer Hilfe durchführen

#### Update funktioniert nicht

Lösung:

1. Im Adminbereich `System-Update` öffnen.
2. Prüfen, ob lokale Änderungen oder Fehler gemeldet werden.
3. Wenn nötig technische Betreuung informieren.

Wichtig:

- Nicht mehrfach blind Updates anstoßen.
- Während eines laufenden Events nur updaten, wenn es zwingend nötig ist.

#### Team oder Produkt falsch angelegt

Lösung für Teams:

1. `Shotcounter` öffnen.
2. Teamnamen korrigieren oder Team löschen.

Lösung für Produkte:

1. `Admin` öffnen.
2. Event-Einstellungen öffnen.
3. Im Tab `Alle Produkte & Kategorien` das Produkt korrigieren.
4. `Speichern` klicken.

### 13.3 Was während des Events nicht ohne Rücksprache gemacht werden soll

- kein `System-Update` im Hochbetrieb
- keine Bilder löschen, die aktuell verwendet werden
- kein aktives Event archivieren, solange noch verkauft oder gezählt wird
- keine Event-JSON importieren, wenn die Wirkung nicht klar ist

## 14. Empfohlene Screenshots für eine Schulungsfassung

Für eine spätere Schulungs- oder Einweisungsfassung sind Screenshots sinnvoll, vor allem für:

1. Startseite ohne aktives Event
2. Adminbereich
3. Neues Event anlegen
4. Event aktivieren
5. Event-Einstellungen mit Tabs
6. Produkteditor
7. Bilderverwaltung
8. Kasse
9. Shotcounter
10. Shotcounter Touch
11. Leaderboard
12. Preisliste
13. Event-Details mit Exporten

Empfohlene Markierung:

- rot für klicken
- gelb für prüfen
- grün für erfolgreich oder fertig
