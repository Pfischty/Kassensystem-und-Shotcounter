#!/usr/bin/env bash
# Startet Kassensystem/Shotcounter für den Eventbetrieb auf einem Mac
# (Ersatz für den Raspberry Pi). Übernimmt, was dort systemd erledigt:
#   - App mit gunicorn auf Port 8000 (statt Flask-Debugserver)
#   - NFC-Bridge, die nach einem Absturz neu startet
#   - Datenbank-Backup alle paar Minuten
#   - Mac schläft nicht ein, solange das Script läuft
# Beenden mit Ctrl+C - stoppt alles wieder.
#
# Einstellungen (optional, als Umgebungsvariable):
#   PORT=8000  BACKUP_INTERVAL_MIN=10  GUNICORN_WORKERS=2  NFC=1 (0 = ohne Kartenleser)

set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${APP_ROOT}"

PORT="${PORT:-8000}"
BACKUP_INTERVAL_MIN="${BACKUP_INTERVAL_MIN:-10}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
NFC="${NFC:-1}"
ENV_FILE="${APP_ROOT}/instance/mac_event.env"
PY="${APP_ROOT}/.venv/bin/python"

if [[ ! -x "${APP_ROOT}/.venv/bin/gunicorn" ]]; then
  echo "Kein venv mit gunicorn gefunden. Einmalig ausführen:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${PORT} ist bereits belegt (läuft die App schon?):" >&2
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >&2
  exit 1
fi

mkdir -p "${APP_ROOT}/instance/logs" "${APP_ROOT}/instance/backups"

# Produktionsbetrieb braucht einen festen SECRET_KEY (sonst sind Logins nach
# jedem Neustart weg). Wird beim ersten Start erzeugt; hier können auch
# ADMIN_USERNAME/ADMIN_PASSWORD ergänzt werden.
if [[ ! -f "${ENV_FILE}" ]]; then
  umask 077
  cat > "${ENV_FILE}" <<EOF
# Umgebung für scripts/mac_event.sh (wird beim Start eingelesen)
SECRET_KEY=$("${PY}" -c 'import secrets; print(secrets.token_hex(32))')
EOF
  echo "Neue ${ENV_FILE} mit SECRET_KEY angelegt."
fi
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a
export APP_ENV=production

PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Beende Hintergrundprozesse ..."
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null || true
  done
  # Bridge stoppen (gibt den Kartenleser frei). Hängt sie im PC/SC-Dienst,
  # reagiert sie nicht auf SIGTERM -> nach 3 s hart beenden, sonst blockiert
  # eine verwaiste Bridge beim nächsten Start die neue.
  if [[ -f instance/nfc_bridge.pid ]]; then
    bridge_pid="$(cat instance/nfc_bridge.pid)"
    kill "${bridge_pid}" 2>/dev/null || true
    for _ in 1 2 3 4 5 6; do
      kill -0 "${bridge_pid}" 2>/dev/null || break
      sleep 0.5
    done
    kill -9 "${bridge_pid}" 2>/dev/null || true
  fi
  "${APP_ROOT}/scripts/backup_db.sh" >/dev/null 2>&1 && echo "Letztes Backup erstellt." || true
}
trap cleanup INT TERM EXIT

# Mac wach halten, solange dieses Script läuft (Bildschirm, Ruhezustand, Netzteil).
caffeinate -dims -w $$ &
PIDS+=($!)

# Regelmässiges DB-Backup (nutzt das gleiche Script wie der Pi).
(
  while sleep $((BACKUP_INTERVAL_MIN * 60)); do
    "${APP_ROOT}/scripts/backup_db.sh" >>"${APP_ROOT}/instance/logs/backup.log" 2>&1 || true
  done
) &
PIDS+=($!)

# NFC-Bridge mit Neustart nach Absturz. Exit-Code 0 = absichtlich gestoppt
# (z. B. über "Bridge stoppen" in /shotcounter/nfc) -> nicht neu starten.
if [[ "${NFC}" == "1" ]]; then
  (
    while true; do
      NFC_BASE_URL="http://127.0.0.1:${PORT}" "${PY}" "${APP_ROOT}/nfc_bridge.py" >/dev/null 2>&1 && break
      sleep 5
    done
  ) &
  PIDS+=($!)
fi

host_name="$(scutil --get LocalHostName 2>/dev/null || hostname -s).local"
lan_ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "?")"
cat <<EOF

Kassensystem & Shotcounter läuft (Ctrl+C zum Beenden)

  Touch (iPad):      http://${host_name}:${PORT}/shotcounter/touch
  Leaderboard:       http://${host_name}:${PORT}/shotcounter/leaderboard
  Kasse:             http://${host_name}:${PORT}/cashier
  Admin:             http://${host_name}:${PORT}/admin
  (falls .local nicht geht: http://${lan_ip}:${PORT})

  NFC-Bridge:        $([[ "${NFC}" == "1" ]] && echo "läuft, Log: instance/logs/nfc_bridge.log" || echo "aus")
  Backups:           alle ${BACKUP_INTERVAL_MIN} min nach instance/backups/

Fragt macOS, ob Python eingehende Verbindungen annehmen darf: "Erlauben" wählen,
sonst erreichen iPad und Leaderboard den Mac nicht.

EOF

"${APP_ROOT}/.venv/bin/gunicorn" -w "${GUNICORN_WORKERS}" -b "0.0.0.0:${PORT}" \
  --access-logfile - "app:app" &
PIDS+=($!)
wait "${PIDS[${#PIDS[@]}-1]}"
