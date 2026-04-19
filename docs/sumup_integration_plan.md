# SumUp Card-Reader Integration Plan

## Zielbild
Wir integrieren SumUp **Card Reader / Terminal Payments** in das Kassensystem, sodass Beträge direkt an ein zugeordnetes Terminal gesendet werden. Standardmäßig ist jede Kasse fest einem Terminal zugeordnet (1:1). Falls kein Terminal zugeteilt ist (oder die Zuweisung nicht mehr aktiv ist), kann die Kasse in der Kassenansicht ein **freies** Terminal auswählen. Mehrere Terminals (typisch 4) arbeiten parallel, aber pro Terminal darf immer nur **eine** Zahlung aktiv sein.

## Scope (MVP)
- Terminal-Setup im Adminbereich
- Feste Zuordnung Kasse ↔ Terminal
- Zahlung an Terminal senden
- Status-Rückmeldung (success/failed/aborted/timeout)
- Logging & Audit-Trail

Out of scope:
- Rückerstattungen/Stornos
- Multi-User-Payment-Queues
- Payment-Splitting

## Architekturüberblick

### Datenmodell (Vorschlag)
1. **Terminal**
   - `id`
   - `name`
   - `sumup_device_id` (oder Reader ID)
   - `active` (bool)
   - `assigned_cashier_id` (1:1 Zuordnung)
   - `created_at`, `updated_at`

2. **PaymentIntent** (oder `TerminalPayment`)
   - `id`
   - `terminal_id`
   - `cashier_id`
   - `amount_cents`
   - `currency`
   - `status` (pending/success/failed/aborted/timeout)
   - `sumup_payment_id`
   - `created_at`, `updated_at`

3. **PaymentLog** (optional)
   - `id`
   - `payment_intent_id`
   - `event` (request_sent/status_update/error)
   - `payload_json`
   - `created_at`

### Service-Schicht
- `sumup_client.py` mit Methoden:
  - `create_terminal_payment(amount, currency, device_id, reference)`
  - `get_payment_status(payment_id)`
- `terminal_payment_service.py` für:
  - Locking pro Terminal (nur eine Zahlung aktiv)
  - Persistenz des PaymentIntents
  - Status-Updates & Timeouts

### Endpoints (Vorschlag)
- `POST /api/terminal-payments` → Startet Zahlung
- `GET /api/terminal-payments/<id>` → Statusabfrage
- `GET /api/terminals` → Liste aktiver Terminals

### UI-Anpassungen
- **Adminbereich**: Terminal-Verwaltung (CRUD)
- **Kasse**:
  - Terminalauswahl, falls keine feste Zuweisung aktiv ist (nur freie Terminals anzeigen)
  - Zahlung „an Terminal senden“ (Button)
  - Statusanzeige (pending/ok/fehler/abgebrochen)

## Sicherheits-/Betriebsaspekte
- API-Credentials sicher in `instance/credentials.json` oder Umgebungsvariablen
- Audit-Logging (wer, wann, welches Terminal, welcher Betrag)
- Terminal-Locking bei parallelen Zahlungen
- Retry-Strategie bei Netzwerkfehlern

## Ablaufdiagramm (vereinfacht)
1. Kasse löst Zahlung aus
2. Backend erstellt PaymentIntent + ruft SumUp API
3. Terminal verarbeitet Zahlung
4. Backend pollt Status / erhält Status-Update
5. Kasse zeigt Ergebnis

## Umsetzungsschritte
1. **SumUp API Zugang / Testumgebung**
2. **Datenmodell & Migration**
3. **Service + API-Endpunkte**
4. **Admin-UI + Kassen-UI**
5. **Logging & Monitoring**
6. **Test mit echten Terminals**

## SumUp API Abgleich (Pflicht)
Vor Umsetzung müssen die geplanten Endpunkte und der Card-Reader-Flow mit der **offiziellen SumUp API-Dokumentation** abgeglichen werden. Insbesondere prüfen:
- Unterstützt der Account **Terminal Payments** / Card-Reader-Flow?
- Exakte API-Endpunkte/SDK und erforderliche Parameter (z. B. Device/Reader ID, Betrag, Referenz)
- Status-Rückmeldungen (Polling oder Webhooks) und mögliche Statuswerte
- Rate-Limits und Timeouts

## Offene Punkte
- Exakte SumUp API-Endpunkte/SDK (je nach Account-Freischaltung)
- Terminal-IDs und Device-Registrierung
- Webhook-Support verfügbar? (optional)
