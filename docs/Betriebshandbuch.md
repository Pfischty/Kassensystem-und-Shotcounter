# Betriebshandbuch

Dieses Handbuch ist für Helferinnen, Helfer und verantwortliche Personen gedacht, die das System während eines Events bedienen. Es beschreibt den normalen Betrieb über die Weboberfläche und vermeidet bewusst technische Details für Terminal, Deployment oder Service-Konfiguration.

Die technische Ergänzung dazu steht in:

- [Event Quickstart](EventQuickstart.md)
- [Initial Setup](InitialSetup.md)
- [Troubleshooting](Troubleshooting.md)
- [Raspberry Pi Deployment](pi_deployment.md)
- [Netzwerkarchitektur](ip_network.md)

## 1. Geräte und Netzwerk Aufbau

Im typischen Eventbetrieb gehören dazu:

- Kassensystem Server (Raspi) (orange)
- PoE Injector
- WLAN Sender (weiss und rund)

- ein oder mehrere Tablets
- optional ein externer Bildschirm für Leaderboard oder Preisliste via Laptop HDMI

## 2. Vorbereitung vor dem Event

### 2.1 Raspberry Pi setup

1. Raspberry Pi mit Strom verbinden.
2. PoE Injector mit Strom verbinden.
3. Raspberry Pi mit `eth0` an den PoE Injector `LAN` anschliessen.
4. WLAN Sender an den PoE Injector an der `POE`-Schnittstelle anschliessen.
5. Warten, bis das System vollständig gestartet ist. (ca. 3 min)

## 3. Schnellstart vor Eventbeginn


1. Raspberry Pi einschalten und mit dem Event-Switch verbinden.
2. Warten, bis das System vollständig gestartet ist.
3. Tablet oder Laptop ebenfalls mit demselben Netz verbinden.
4. Falls auch das nicht funktioniert, `http://192.168.50.1:8000` verwenden.

![QR-Code für http://192.168.50.1:8000](assets/qr_kassensystem_192_168_50_1_8000.png){ width=200px }

Direktdateien:

- [PNG](assets/qr_kassensystem_192_168_50_1_8000.png)
- [SVG](assets/qr_kassensystem_192_168_50_1_8000.svg)

5. Prüfen, ob ein aktives Event vorhanden ist.

Wenn die Startseite `Kein aktives Event` zeigt, ist das kein Systemfehler. Es muss zuerst im Adminbereich ein Event aktiviert werden.


### 3.1 Browsertest

1. Auf einem Gerät im Event-Netz den Browser öffnen.
2. `http://192.168.50.1:8000` öffnen.

## 4. Anwenden gemäss learning by doing

## 5. Eventabschluss

### 5.1 Eventdetails öffnen

1. In `Übersicht` oder Admin das Event wählen.
2. `Details` oder die Statistik- und Log-Ansicht öffnen.

### 5.2 CSV-Exporte herunterladen

Auf der Event-Detailseite stehen je nach Funktion unter anderem:

- `Abschlüsse / Bestell-Log`
- `Verkaufte Getränke`
- `Shot-Log`

Diese Dateien eignen sich für:

- Abrechnung
- Nachkontrolle
- Archiv

### 5.3 Event archivieren

1. Im Adminbereich das Event suchen.
2. Den Status-Button `Aktiv - Archivieren` klicken.

Erwartetes Ergebnis:

- Das Event ist nicht mehr aktiv.
- Kasse und Shotcounter sind für dieses Event beendet.

Wichtig:

- Ein aktives Event nur archivieren, wenn wirklich nicht mehr verkauft oder gezählt wird.

### 5.4 Neues Event aus Vorlage erstellen

1. `+ Neues Event` wählen.
2. Im Feld `Vorlage kopieren` ein altes Event wählen.
3. `Übernehmen` klicken.
4. Event anlegen.
5. Aktivieren.

## 6. Notfallseite

### 6.1 Wenn gar nichts mehr klar ist

Diese Reihenfolge immer zuerst prüfen:

1. Verbunden mit dem Richtigen WLAN -> 90% löst das den Fehler
2. Gibt es ein aktives Event?


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

### 6.2 Was während des Events nicht ohne Rücksprache gemacht werden soll

- kein `System-Update` im Hochbetrieb
- keine Bilder löschen, die aktuell verwendet werden
- kein aktives Event archivieren, solange noch verkauft oder gezählt wird
- keine Event-JSON importieren, wenn die Wirkung nicht klar ist
