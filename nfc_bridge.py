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
import signal
import sys
import threading
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

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - Sperre wird dann einfach übersprungen
    PSUTIL_AVAILABLE = False


REPO_ROOT = Path(__file__).resolve().parent
GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]

BASE_URL = os.environ.get("NFC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SECRET_FILE = Path(os.environ.get("NFC_SECRET_FILE", REPO_ROOT / "instance" / "nfc_secret.txt"))
PID_FILE = Path(os.environ.get("NFC_PID_FILE", REPO_ROOT / "instance" / "nfc_bridge.pid"))
POLL_INTERVAL = float(os.environ.get("NFC_POLL_INTERVAL", "0.5"))
HEARTBEAT_INTERVAL = float(os.environ.get("NFC_HEARTBEAT_INTERVAL", "5"))
# Eine Karte gilt erst als abgehoben, wenn sie so lange am Stück nicht mehr
# gelesen werden konnte. Kurze Aussetzer (Karte am Rand des Lesefelds,
# "Card is unresponsive", Leser kurz weg vom USB) lösen so keinen neuen Scan aus.
REMOVAL_GRACE = float(os.environ.get("NFC_REMOVAL_GRACE", "1.0"))
# Hängt ein Durchlauf der Lese-Schleife länger als das, beendet sich der
# Prozess selbst, damit systemd bzw. scripts/mac_event.sh ihn neu startet.
# Grund: Unter macOS kann SCardConnect im PC/SC-Dienst dauerhaft blockieren -
# der Prozess lebt dann scheinbar, meldet aber keine Karten mehr und reagiert
# auch nicht auf SIGTERM (Python-Signalhandler laufen erst nach dem C-Aufruf).
WATCHDOG_TIMEOUT = float(os.environ.get("NFC_WATCHDOG_TIMEOUT", "15"))
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


def acquire_single_instance_lock() -> None:
    """Verhindert zwei gleichzeitig laufende Bridge-Prozesse.

    Egal ob per systemd-Dienst, per Web-GUI-Button (nfc_bridge_manager.py)
    oder manuell im Terminal gestartet — alle Wege benutzen dieselbe
    PID-Datei. Läuft bereits eine gültige Instanz, beendet sich dieser
    Prozess sofort, statt sich mit der anderen um den Leser zu streiten.
    Ohne 'psutil' wird die Prüfung übersprungen (keine harte Abhängigkeit
    für die Kernfunktion).
    """

    if not PSUTIL_AVAILABLE:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing_pid = None
        if existing_pid and psutil.pid_exists(existing_pid):
            try:
                cmdline = " ".join(psutil.Process(existing_pid).cmdline())
            except psutil.Error:
                cmdline = ""
            if "nfc_bridge.py" in cmdline:
                logger.error(
                    "Es läuft bereits eine NFC-Bridge (PID %s). Beende diesen Prozess, "
                    "um doppelte Kartenleser-Zugriffe zu vermeiden.",
                    existing_pid,
                )
                raise SystemExit(1)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release_single_instance_lock() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_FILE.unlink()
    except OSError:
        pass


def _handle_sigterm(signum, frame) -> None:  # noqa: ARG001 - Signatur von signal.signal vorgegeben
    raise SystemExit(0)


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


def _describe_post_error(exc: Exception) -> str:
    """Übersetzt einen HTTP-Fehler in eine Meldung, die direkt zur Ursache führt.

    Ein 403 sieht auf den ersten Blick wie ein Erreichbarkeitsproblem aus,
    ist aber praktisch immer ein Token-Mismatch mit instance/nfc_secret.txt
    (z. B. weil die Datei neu erzeugt wurde, während die App schon lief).
    """

    if isinstance(exc, error.HTTPError) and exc.code == 403:
        return (
            f"{exc} - Die App nimmt Scans nur über 127.0.0.1 und mit dem Token aus "
            f"{SECRET_FILE} an. Ziel-App ist {BASE_URL}: Zeigt das nicht auf 127.0.0.1/localhost, "
            "NFC_BASE_URL korrigieren; sonst prüfen, ob Bridge und App dasselbe instance/-Verzeichnis sehen."
        )
    return str(exc)


def send_scan(uid: str, token: str) -> None:
    try:
        _post_json("/internal/nfc/scan", {"uid": uid}, token)
        logger.info("Scan gemeldet: UID=%s", uid)
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        logger.warning("Scan konnte nicht gemeldet werden: %s", _describe_post_error(exc))


def send_heartbeat(token: str, reader_name: str | None, error_message: str | None = None) -> None:
    try:
        _post_json(
            "/internal/nfc/heartbeat",
            {"reader_name": reader_name or "", "error": error_message or ""},
            token,
        )
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        logger.debug("Heartbeat konnte nicht gemeldet werden: %s", _describe_post_error(exc))


class CardPresence:
    """Merkt sich, welche Karte gerade auf dem Leser liegt.

    Jede Karte wird genau einmal pro Auflegen gemeldet. Als abgehoben gilt
    sie erst nach REMOVAL_GRACE Sekunden ohne erfolgreichen Lesevorgang.
    """

    def __init__(self, removal_grace: float = REMOVAL_GRACE) -> None:
        self.removal_grace = removal_grace
        self.current_uid: str | None = None
        self.last_seen_at = 0.0

    def seen(self, uid: str, now: float) -> bool:
        """Karte gelesen. True, wenn sie neu aufgelegt wurde und gemeldet werden soll."""

        is_new = uid != self.current_uid
        self.current_uid = uid
        self.last_seen_at = now
        return is_new

    def not_seen(self, now: float) -> None:
        """In diesem Durchlauf keine Karte lesbar (keine Karte, Lesefehler, kein Leser)."""

        if self.current_uid and now - self.last_seen_at >= self.removal_grace:
            self.current_uid = None


def _is_transient_card_error(exc: Exception) -> bool:
    """Karte nur halb im Feld bzw. gerade abgehoben - normal, kein Grund für eine Warnung."""

    message = str(exc).lower()
    return "unresponsive" in message or "removed" in message or "no smart card" in message


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


CONFLICTING_KERNEL_MODULES = {"pn533_usb", "pn533", "nfc"}


def detect_kernel_driver_conflict() -> str | None:
    """Erkennt den häufigsten Linux/Raspberry-Pi-Stolperstein mit dem ACR122U.

    Der ACR122U basiert auf dem PN532-Chipsatz. Der Linux-Kernel bringt dafür
    ein eigenes NFC-Subsystem mit (Treiber `pn533_usb`), das dieselbe USB-ID
    kennt und die Schnittstelle automatisch beansprucht — bevor `pcscd` per
    libusb zugreifen kann. Ergebnis: `lsusb` zeigt den Leser an, aber
    `pcsc_scan`/pyscard finden ihn nie oder er flackert. Der zuverlässige Fix
    ist, dem Kernel das Binden per Modul-Blacklist zu verbieten (siehe
    `scripts/pi_manage.sh nfc-fix-kernel-driver` und docs/pi_deployment.md).

    Rein informativ auf Nicht-Linux-Systemen (kein /proc/modules) -> None.
    """

    proc_modules = Path("/proc/modules")
    if not proc_modules.exists():
        return None
    try:
        content = proc_modules.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    loaded = {line.split()[0] for line in content.splitlines() if line.strip()}
    conflicting = sorted(loaded & CONFLICTING_KERNEL_MODULES)
    if not conflicting:
        return None
    return (
        f"Kernel-NFC-Treiber geladen ({', '.join(conflicting)}) - blockiert vermutlich den ACR122U. "
        "Fix: sudo ./scripts/pi_manage.sh nfc-fix-kernel-driver (danach ggf. neu starten). "
        "Details: docs/pi_deployment.md, Abschnitt 'NFC-Kartenleser'"
    )


class Watchdog:
    """Beendet den Prozess, wenn die Lese-Schleife zu lange nicht vorankommt."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.last_beat = time.monotonic()

    def beat(self) -> None:
        self.last_beat = time.monotonic()

    def start(self) -> None:
        if self.timeout <= 0:
            return
        threading.Thread(target=self._run, name="nfc-watchdog", daemon=True).start()

    def _run(self) -> None:
        while True:
            time.sleep(1)
            stalled_for = time.monotonic() - self.last_beat
            if stalled_for > self.timeout:
                logger.error(
                    "Lese-Schleife hängt seit %.0f s (vermutlich im PC/SC-Dienst). "
                    "Beende die Bridge für einen Neustart.",
                    stalled_for,
                )
                release_single_instance_lock()
                logging.shutdown()
                # os._exit statt sys.exit: der Hauptthread steckt in einem C-Aufruf fest.
                os._exit(3)


def main() -> None:
    logger.info("NFC-Bridge gestartet. Ziel-App: %s", BASE_URL)
    watchdog = Watchdog(WATCHDOG_TIMEOUT)
    watchdog.start()

    presence = CardPresence()
    last_logged_error: str | None = None
    last_heartbeat_at: float = 0.0
    last_warned_no_token = False
    last_warned_no_reader = False
    last_selected_reader: str | None = None

    while True:
        watchdog.beat()
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
                kernel_conflict = detect_kernel_driver_conflict()
                no_reader_message = kernel_conflict or "Kein Leser gefunden"
                if not last_warned_no_reader:
                    if kernel_conflict:
                        logger.error("Kein PC/SC-Leser gefunden. %s", kernel_conflict)
                    else:
                        logger.warning("Kein PC/SC-Leser gefunden. Ist der ACR122U angeschlossen?")
                    last_warned_no_reader = True
                presence.not_seen(time.time())
                last_selected_reader = None
                if time.time() - last_heartbeat_at > HEARTBEAT_INTERVAL:
                    send_heartbeat(token, None, no_reader_message)
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

            uid = None
            connection = active_reader.createConnection()
            try:
                connection.connect()
            except NoCardException:
                pass
            except CardConnectionException as exc:
                # "unresponsive" = Karte nur halb im Feld -> normal. Alles andere
                # (Leser getrennt, exklusiv belegt) nur einmal pro Fehlerbild
                # loggen statt alle 0,5 s.
                if not _is_transient_card_error(exc) and str(exc) != last_logged_error:
                    logger.warning("Verbindung zum Leser fehlgeschlagen: %s", exc)
                    last_logged_error = str(exc)
            else:
                try:
                    uid = get_uid(connection)
                except CardConnectionException as exc:
                    if not _is_transient_card_error(exc):
                        logger.warning("Karte konnte nicht gelesen werden: %s", exc)
                try:
                    connection.disconnect()
                except CardConnectionException:
                    pass

            now = time.time()
            if uid:
                last_logged_error = None
                if presence.seen(uid, now):
                    send_scan(uid, token)
            else:
                presence.not_seen(now)

            if time.time() - last_heartbeat_at > HEARTBEAT_INTERVAL:
                send_heartbeat(token, reader_name)
                last_heartbeat_at = time.time()

        except Exception as exc:  # noqa: BLE001 - Event darf wegen Hardware-Hakeln nicht sterben
            logger.error("Unerwarteter Fehler in der Lese-Schleife: %s", exc)
            presence.not_seen(time.time())
            try:
                send_heartbeat(token, reader_name, str(exc))
                last_heartbeat_at = time.time()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    acquire_single_instance_lock()
    try:
        main()
    except KeyboardInterrupt:
        logger.info("NFC-Bridge beendet (KeyboardInterrupt).")
    except SystemExit:
        logger.info("NFC-Bridge beendet (SIGTERM/SystemExit).")
    finally:
        release_single_instance_lock()
