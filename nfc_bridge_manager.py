"""Verwaltet den Lebenszyklus des NFC-Bridge-Kindprozesses aus der Web-App heraus.

Für den Dauerbetrieb auf dem Pi bleibt der systemd-Dienst
(`kassensystem-nfc.service`, siehe `scripts/pi_manage.sh`) die empfohlene
Lösung: Start beim Booten, automatischer Neustart bei Absturz, unabhängig vom
Lebenszyklus der Web-App. Dieses Modul ergänzt das für lokales Testen ohne
systemd — etwa auf macOS oder Windows, wo es kein systemd gibt — per Klick
auf `/shotcounter/nfc`, ohne ein zweites Terminal öffnen zu müssen.

Alle Startwege (systemd, dieser Manager, manuelles `python nfc_bridge.py`)
benutzen dieselbe PID-Datei als Sperre (siehe `nfc_bridge.py`), damit nie
zwei Instanzen gleichzeitig denselben Kartenleser beanspruchen — unabhängig
davon, welcher Weg zuerst da war.

Nutzt `psutil` für plattformunabhängige Prozesssteuerung (macOS/Linux/
Windows/Pi). Ist `psutil` nicht installiert, geben alle Funktionen einen
klaren Fehler zurück, statt die komplette Web-App beim Import zum Absturz
zu bringen — das NFC-Feature ist damit weiterhin optional und darf den
Kassenbetrieb nie gefährden.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - nur bei fehlender Abhängigkeit
    PSUTIL_AVAILABLE = False

REPO_ROOT = Path(__file__).resolve().parent
BRIDGE_SCRIPT = REPO_ROOT / "nfc_bridge.py"

_PSUTIL_MISSING_MESSAGE = (
    "Paket 'psutil' ist nicht installiert. Bitte im venv ausführen: "
    "pip install -r requirements.txt"
)


def _pid_file(instance_path: str) -> Path:
    return Path(instance_path) / "nfc_bridge.pid"


def _read_pid(pid_file: Path) -> int | None:
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _is_bridge_process(pid: int) -> bool:
    try:
        proc = psutil.Process(pid)
        return "nfc_bridge.py" in " ".join(proc.cmdline())
    except psutil.Error:
        return False


def bridge_status(instance_path: str) -> tuple[bool, int | None]:
    """Prüft anhand der PID-Datei UND einer laufenden Prozessliste, ob eine
    Bridge aktiv ist — nicht nur ob die Datei existiert (die könnte von einem
    längst beendeten, nicht sauber aufgeräumten Prozess übrig sein, z. B.
    nach einem harten Kill unter Windows)."""

    if not PSUTIL_AVAILABLE:
        return False, None
    pid = _read_pid(_pid_file(instance_path))
    if pid and psutil.pid_exists(pid) and _is_bridge_process(pid):
        return True, pid
    return False, None


def start_bridge(instance_path: str, base_url: str) -> tuple[bool, str, int | None]:
    """Startet nfc_bridge.py als eigenständigen Kindprozess.

    `base_url` wird typischerweise aus der eingehenden HTTP-Anfrage
    übernommen (`request.host_url`), damit die Bridge automatisch denselben
    Host/Port anspricht, unter dem die Web-App gerade erreichbar ist — ohne
    dass man Umgebungsvariablen von Hand setzen muss.
    """

    if not PSUTIL_AVAILABLE:
        return False, _PSUTIL_MISSING_MESSAGE, None

    running, pid = bridge_status(instance_path)
    if running:
        return True, f"Läuft bereits (PID {pid}).", pid

    if not BRIDGE_SCRIPT.exists():
        return False, "nfc_bridge.py wurde im Projektverzeichnis nicht gefunden.", None

    env = dict(os.environ)
    env["NFC_BASE_URL"] = base_url.rstrip("/")
    env.setdefault("NFC_SECRET_FILE", str(Path(instance_path) / "nfc_secret.txt"))
    env.setdefault("NFC_PID_FILE", str(_pid_file(instance_path)))
    log_dir = Path(instance_path) / "logs"
    env.setdefault("NFC_LOG_DIR", str(log_dir))

    popen_kwargs: dict = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        # Eigene Datei statt nfc_bridge.log: Das Skript schreibt seine Logs
        # bereits selbst dorthin (RotatingFileHandler) UND spiegelt sie nach
        # stdout (damit systemd/journald sie auch sieht). Würden wir stdout
        # hier zusätzlich in dieselbe Datei umleiten, stünde jede Zeile
        # doppelt drin. Diese Datei fängt nur das ab, was den Logger gar
        # nicht erst erreicht (z. B. ein Traceback beim Modul-Import).
        log_fh = open(log_dir / "nfc_bridge_process.log", "a", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                [sys.executable, str(BRIDGE_SCRIPT)],
                cwd=str(REPO_ROOT),
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                **popen_kwargs,
            )
        finally:
            # Das Kind hat beim Start seinen eigenen Duplikat-Filedeskriptor
            # erhalten; das Elternteil (Web-App) muss seinen nicht offen halten.
            log_fh.close()
    except OSError as exc:
        return False, f"Start fehlgeschlagen: {exc}", None

    return True, f"Gestartet (PID {proc.pid}).", proc.pid


def stop_bridge(instance_path: str, timeout: float = 5.0) -> tuple[bool, str]:
    if not PSUTIL_AVAILABLE:
        return False, _PSUTIL_MISSING_MESSAGE

    running, pid = bridge_status(instance_path)
    if not running or not pid:
        return True, "War nicht aktiv."

    try:
        proc = psutil.Process(pid)
        proc.terminate()
        _gone, alive = psutil.wait_procs([proc], timeout=timeout)
        if alive:
            proc.kill()
    except psutil.Error as exc:
        return False, f"Stoppen fehlgeschlagen: {exc}"

    pid_file = _pid_file(instance_path)
    try:
        if _read_pid(pid_file) == pid:
            pid_file.unlink(missing_ok=True)
    except OSError:
        pass
    return True, "Gestoppt."
