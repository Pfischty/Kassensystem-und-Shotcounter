# Event Quickstart

Diese Seite ist für den schnellen Start am Event gedacht. Sie enthält nur die wichtigsten Schritte für Helferinnen und Helfer.

Weitere Dokumente:

- [Betriebshandbuch](Betriebshandbuch.md)
- [Troubleshooting](Troubleshooting.md)

## 1. WLAN verbinden

Falls das Gerät noch nicht im Event-Netz ist, zuerst den WLAN-QR-Code scannen:

![QR-Code für das Event-WLAN](assets/qr_wifi_nsa_proxy.png)

Alternativ direkt öffnen:

- [WLAN-QR als PNG](assets/qr_wifi_nsa_proxy.png)
- [WLAN-QR als SVG](assets/qr_wifi_nsa_proxy.svg)

## 2. Kasse öffnen

Danach den QR-Code für die Kasse scannen:

![QR-Code für die Kasse](assets/qr_kassensystem_cashier_192_168_50_1_8000.png)

Direktlink zur Kasse:

- [Kasse öffnen](http://192.168.50.1:8000/cashier)

Alternativ direkt öffnen:

- [Kassen-QR als PNG](assets/qr_kassensystem_cashier_192_168_50_1_8000.png)
- [Kassen-QR als SVG](assets/qr_kassensystem_cashier_192_168_50_1_8000.svg)

## 3. Falls die Kasse nicht lädt

In dieser Reihenfolge prüfen:

1. Ist das Gerät wirklich mit dem Event-WLAN verbunden?
2. Lädt `http://192.168.50.1:8000/cashier` im Browser?
3. Ist der Raspberry Pi eingeschaltet?
4. Wurde lange genug gewartet, bis das System vollständig gestartet ist?
5. Falls weiterhin nichts funktioniert, verantwortliche Person holen.

## 4. Für Verantwortliche

Wenn kein aktives Event vorhanden ist, zuerst den Adminbereich öffnen:

- [Admin öffnen](http://192.168.50.1:8000/admin)

Danach Event aktivieren und erst dann die Kasse benutzen.
