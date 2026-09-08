"""NFC-Bridge für den ACR122U-Kartenleser.

Dieses Skript läuft als eigenständiger Prozess (empfohlen: eigener
systemd-Dienst `kassensystem-nfc.service`, siehe deploy/ und
scripts/pi_manage.sh) und liest fortlaufend die UID von Karten, die auf
einen angeschlossenen PC/SC-Leser (z. B. ACS ACR122U) gelegt werden.

Warum ein eigener Prozess statt eines Threads in app.py?
- Gunicorn startet die Web-App standardmäßig mit mehreren Workern
  (siehe scripts/pi_manage.sh, GUNICORN_WORKERS). Ein Hintergrund-Thread
  pro Worker würde denselben Leser mehrfach gleichzeitig ansprechen.
- Der Leserzugriff (PC/SC) ist unabhängig vom Webserver und soll auch
  überleben, wenn Gunicorn neu startet, und umgekehrt.

Die erkannte UID wird per HTTP an die laufende Flask-App gemeldet
(POST /internal/nfc/scan), authentifiziert über ein gemeinsames Secret
in instance/nfc_secret.txt (wird von app.py beim ersten Start erzeugt).
Die App entscheidet dann, ob gerade eine "Karte anlernen"-Anfrage aktiv
ist (Karte wird einem Team zugeordnet) oder ob es sich um einen
normalen Scan im Festbetrieb handelt (Popup zum Shots-Buchen).

Es wird bewusst nur die UID der Karte verwendet (kein Beschreiben des
Kartenspeichers). Das funktioniert mit praktisch jeder ISO14443-Karte
oder jedem NFC-Wristband, benötigt keine Mifare-Schlüsselverwaltung und
ist damit deutlich robuster für den Eventbetrieb als ein Schreibzugriff
auf den Kartenspeicher.

Benötigt: `pyscard` (siehe requirements.txt) sowie einen laufenden
PC/SC-Dienst (Linux: `pcscd`, macOS: eingebaut).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib import error, request

try:
    from smartcard.Exceptions import CardConnectionException, NoCardException
    from smartcard.pcsc.PCSCExceptions import EstablishContextException, ListReadersException
    from smartcard.System import readers
    from smartcard.util import toHexString
except ImportError:  # pragma: no cover - klare Fehlermeldung statt Traceback
    print(
        "Fehler: Paket 'pyscard' ist nicht installiert. "
        "Bitte im Projekt-venv ausführen: pip install pyscard",
        file=sys.stderr,
    )
    raise SystemExit(1)


REPO_ROOT = Path(__file__).resolve().parent
GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]

BASE_URL = os.environ.get("NFC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SECRET_FILE = Path(os.environ.get("NFC_SECRET_FILE", REPO_ROOT / "instance" / "nfc_secret.txt"))
POLL_INTERVAL = float(os.environ.get("NFC_POLL_INTERVAL", "0.5"))
HEARTBEAT_INTERVAL = float(os.environ.get("NFC_HEARTBEAT_INTERVAL", "5"))
SCAN_DEBOUNCE = float(os.environ.get("NFC_SCAN_DEBOUNCE", "3"))
REQUEST_TIMEOUT = float(os.environ.get("NFC_HTTP_TIMEOUT", "3"))

# Auf jeder Instanz (Entwicklungs-Mac, verschiedene Raspberry-Pis am Event)
# wird der Leser nicht über einen festen USB-Pfad angesprochen, sondern über
# PC/SC autoerkannt (Treiber meldet ihn beim System an, unabhängig vom
# USB-Port). Ist mehr als ein Leser angeschlossen, wird bevorzugt einer
# gewählt, dessen Name zu NFC_READER_NAME_FILTER passt (Standard: ACR122U);
# so bleibt die Auswahl auf jeder Maschine gleich, auch wenn dort z. B.
# zusätzlich ein interner Kartenleser existiert.
READER_NAME_FILTER = os.environ.get("NFC_READER_NAME_FILTER", "ACR122").strip().lower()

log_dir = Path(os.environ.get("NFC_LOG_DIR", REPO_ROOT / "instance" / "logs"))
log_dir.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("nfc_bridge")
logger.setLevel(logging.INFO)
_file_handler = RotatingFileHandler(log_dir / "nfc_bridge.log", maxBytes=512_000, backupCount=3)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_file_handler)
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_stream_handler)


def _load_token() -> str | None:
    try:
        token = SECRET_FILE.read_text(encoding="utf-8").strip()
        return token or None
    except OSError:
        return None


def _post_json(path: str, payload: dict, token: str) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Nfc-Token": token},
    )
    with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        resp.read()


def send_scan(uid: str, token: str) -> None:
    try:
        _post_json("/internal/nfc/scan", {"uid": uid}, token)
        logger.info("Scan gemeldet: UID=%s", uid)
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        logger.warning("Scan konnte nicht gemeldet werden (App erreichbar?): %s", exc)


def send_heartbeat(token: str, reader_name: str | None, error_message: str | None = None) -> None:
    try:
        _post_json(
            "/internal/nfc/heartbeat",
            {"reader_name": reader_name or "", "error": error_message or ""},
            token,
        )
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        logger.debug("Heartbeat konnte nicht gemeldet werden: %s", exc)


def get_uid(connection) -> str | None:
    data, sw1, sw2 = connection.transmit(GET_UID_APDU)
    if sw1 == 0x90 and sw2 == 0x00 and data:
        return toHexString(data).replace(" ", "")
    return None


def select_reader(available: list) -> tuple[object, str | None]:
    """Wählt den anzusprechenden Leser aus allen von PC/SC gemeldeten Lesern.

    Bevorzugt einen Leser, dessen Name zu NFC_READER_NAME_FILTER passt
    (Standard "acr122"), damit auf jeder Instanz (verschiedene Pis, Dev-Mac,
    ggf. mehrere angeschlossene Leser) deterministisch derselbe physische
    Leser gewählt wird statt eines zufälligen ersten Eintrags. Gibt es keinen
    passenden Treffer, wird der erste verfügbare Leser genutzt und eine
    Warnung zurückgegeben, damit das im Log sichtbar wird.
    """

    if not available:
        return None, None

    if READER_NAME_FILTER:
        for candidate in available:
            if READER_NAME_FILTER in str(candidate).lower():
                return candidate, None

    fallback = available[0]
    warning = None
    if READER_NAME_FILTER:
        warning = (
            f"Kein Leser mit Namen passend zu '{READER_NAME_FILTER}' gefunden. "
            f"Nutze stattdessen '{fallback}'. Verfügbar: {[str(r) for r in available]}"
        )
    return fallback, warning


def main() -> None:
    logger.info("NFC-Bridge gestartet. Ziel-App: %s", BASE_URL)

    last_uid: str | None = None
    last_scan_at: float = 0.0
    last_heartbeat_at: float = 0.0
    last_warned_no_token = False
    last_warned_no_reader = False
    last_selected_reader: str | None = None

    while True:
        token = _load_token()
        if not token:
            if not last_warned_no_token:
                logger.warning(
                    "Kein Shared-Secret gefunden (%s). Warte, bis die Web-App einmal gestartet wurde.",
                    SECRET_FILE,
                )
                last_warned_no_token = True
            time.sleep(2)
            continue
        last_warned_no_token = False

        reader_name = None
        try:
            try:
                available = readers()
            except (EstablishContextException, ListReadersException) as exc:
                # Typischerweise: pcscd läuft nicht (Linux) bzw. PC/SC-Dienst
                # ist auf dieser Instanz nicht erreichbar.
                if not last_warned_no_reader:
                    logger.error(
                        "PC/SC-Dienst nicht erreichbar (läuft 'pcscd'? siehe "
                        "docs/pi_deployment.md): %s",
                        exc,
                    )
                    last_warned_no_reader = True
                if time.time() - last_heartbeat_at > HEARTBEAT_INTERVAL:
                    send_heartbeat(token, None, f"PC/SC-Dienst nicht erreichbar: {exc}")
                    last_heartbeat_at = time.time()
                time.sleep(2)
                continue

            if not available:
                if not last_warned_no_reader:
                    logger.warning("Kein PC/SC-Leser gefunden. Ist der ACR122U angeschlossen?")
                    last_warned_no_reader = True
                last_uid = None
                last_selected_reader = None
                if time.time() - last_heartbeat_at > HEARTBEAT_INTERVAL:
                    send_heartbeat(token, None, "Kein Leser gefunden")
                    last_heartbeat_at = time.time()
                time.sleep(2)
                continue
            last_warned_no_reader = False

            active_reader, selection_warning = select_reader(available)
            if selection_warning:
                logger.warning(selection_warning)
            reader_name = str(active_reader)
            if reader_name != last_selected_reader:
                logger.info("Verwende Leser: %s", reader_name)
                last_selected_reader = reader_name
                last_uid = None  # neuer/anderer Leser -> Debounce zurücksetzen

            connection = active_reader.createConnection()
            try:
                connection.connect()
            except NoCardException:
                last_uid = None  # Karte abgehoben -> nächstes Auflegen löst wieder aus
            except CardConnectionException as exc:
                # z. B. Leser wurde während des Verbindungsaufbaus getrennt,
                # oder ist exklusiv durch einen anderen Prozess belegt.
                logger.warning("Verbindung zum Leser fehlgeschlagen: %s", exc)
                last_uid = None
            else:
                try:
                    uid = get_uid(connection)
                except CardConnectionException as exc:
                    logger.warning("Karte konnte nicht gelesen werden (evtl. abgehoben): %s", exc)
                    uid = None
                if uid:
                    now = time.time()
                    if uid != last_uid or (now - last_scan_at) > SCAN_DEBOUNCE:
                        send_scan(uid, token)
                        last_scan_at = now
                    last_uid = uid
                try:
                    connection.disconnect()
                except CardConnectionException:
                    pass

            if time.time() - last_heartbeat_at > HEARTBEAT_INTERVAL:
                send_heartbeat(token, reader_name)
                last_heartbeat_at = time.time()

        except Exception as exc:  # noqa: BLE001 - Event darf wegen Hardware-Hakeln nicht sterben
            logger.error("Unerwarteter Fehler in der Lese-Schleife: %s", exc)
            last_uid = None
            try:
                send_heartbeat(token, reader_name, str(exc))
                last_heartbeat_at = time.time()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("NFC-Bridge beendet (KeyboardInterrupt).")
