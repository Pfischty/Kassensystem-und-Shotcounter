#!/usr/bin/env bash

# Pi maintenance helper for Kassensystem und Shotcounter.
# This script assumes it is stored inside the project repo.
#
# Highlights
# - Create/refresh a virtualenv (supports offline installs via ./wheels/)
# - Write & enable a systemd service for auto-start after reboot
# - Update the app from Git and restart the service
# - Minimal Wi‑Fi helpers for maintenance access
#
# Usage examples:
#   ./scripts/pi_manage.sh create-venv
#   ./scripts/pi_manage.sh install-deps [--offline]
#   sudo ./scripts/pi_manage.sh write-service --port 8000
#   sudo ./scripts/pi_manage.sh enable-service
#   sudo ./scripts/pi_manage.sh update --branch main
#   sudo ./scripts/pi_manage.sh wifi-add SSID PASS
#   sudo ./scripts/pi_manage.sh wifi-up
#   sudo ./scripts/pi_manage.sh wifi-down

set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="kassensystem-shotcounter"
BACKUP_SERVICE_NAME="kassensystem-backup"
KIOSK_SERVICE_NAME="kassensystem-kiosk"
ENV_FILE="/etc/kassensystem.env"
WHEEL_DIR="${APP_ROOT}/wheels"
DEFAULT_PORT="${PORT:-8000}"
SERVICE_USER="${SERVICE_USER:-kassensystem}"

usage() {
  cat <<'EOF'
Pi maintenance helper

Commands:
  create-venv                 Create a Python virtualenv in .venv
  install-deps [--offline] [--dev]  Install requirements.txt (uses ./wheels if --offline)
  write-service [--port N]    Write systemd unit to /etc/systemd/system/*.service
  enable-service              systemctl daemon-reload + enable --now
  disable-service             systemctl disable --now
  update [--branch BR] [--offline]  Pull Git (unless --offline), install deps, restart service
  write-backup                Write systemd service + timer for DB backups
  enable-backup               Enable and start the backup timer
  disable-backup              Disable the backup timer
  write-kiosk                 Write systemd service for Chromium kiosk
  enable-kiosk                Enable and start the kiosk service
  disable-kiosk               Disable the kiosk service
  wifi-add SSID PASS          Append Wi‑Fi network to wpa_supplicant and reconfigure
  wifi-up                     Bring wlan0 up and reconfigure
  wifi-down                   Bring wlan0 down
  status                      Show service status
EOF
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Bitte als root (sudo) ausführen." >&2
    exit 1
  fi
}

ensure_venv() {
  if [[ ! -x "${APP_ROOT}/.venv/bin/python" ]]; then
    echo "Erzeuge virtuelles Environment unter ${APP_ROOT}/.venv ..."
    python -m venv "${APP_ROOT}/.venv"
  fi
}

ensure_service_user() {
  require_root
  if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    echo "Erstelle System-User ${SERVICE_USER} ..."
    useradd --system --home "${APP_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}"
  fi
  mkdir -p "${APP_ROOT}/instance/logs" "${APP_ROOT}/instance/backups"
  chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_ROOT}/instance"
}

install_deps() {
  local offline=0
  local dev=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --offline) offline=1; shift ;;
      --dev) dev=1; shift ;;
      *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
    esac
  done

  ensure_venv
  local pip="${APP_ROOT}/.venv/bin/pip"
  local req_file="${APP_ROOT}/requirements.txt"
  if [[ $dev -eq 1 ]]; then
    req_file="${APP_ROOT}/requirements-dev.txt"
  fi

  if [[ $offline -eq 1 ]]; then
    echo "Installiere Abhängigkeiten offline (verwende ${WHEEL_DIR}) ..."
    "${pip}" install --no-index --find-links="${WHEEL_DIR}" -r "${req_file}"
  else
    echo "Installiere Abhängigkeiten online ..."
    "${pip}" install --upgrade pip
    "${pip}" install -r "${req_file}"
  fi
}

write_env_file() {
  require_root
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Erzeuge ${ENV_FILE} (du kannst Werte später anpassen) ..."
    cat > "${ENV_FILE}" <<EOF
# Environment für Kassensystem/Shotcounter
FLASK_ENV=production
APP_ENV=production
SECRET_KEY=$(openssl rand -hex 16)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$(openssl rand -hex 8)
BACKUP_DIR=${APP_ROOT}/instance/backups
BACKUP_RETENTION=14
GUNICORN_WORKERS=2
EOF
    chmod 600 "${ENV_FILE}"
  else
    echo "${ENV_FILE} existiert bereits – unverändert gelassen."
  fi
}

write_service() {
  require_root
  ensure_service_user
  local port="${DEFAULT_PORT}"
  local gunicorn_workers="${GUNICORN_WORKERS:-2}"
  local protect_home="true"
  if [[ "${APP_ROOT}" == /home/* || "${APP_ROOT}" == /root/* ]]; then
    protect_home="false"
  fi
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
    esac
  done

  write_env_file
  cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Kassensystem und Shotcounter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${ENV_FILE}
WorkingDirectory=${APP_ROOT}
User=${SERVICE_USER}
Group=${SERVICE_USER}
ExecStart=${APP_ROOT}/.venv/bin/gunicorn -w ${gunicorn_workers} -b 0.0.0.0:${port} "app:app"
Restart=always
RestartSec=5
TimeoutStartSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=${protect_home}
ReadWritePaths=${APP_ROOT}/instance
UMask=0077

[Install]
WantedBy=multi-user.target
EOF

  echo "Unit /etc/systemd/system/${SERVICE_NAME}.service geschrieben."
}

enable_service() {
  require_root
  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}.service"
  systemctl status --no-pager "${SERVICE_NAME}.service"
}

disable_service() {
  require_root
  systemctl disable --now "${SERVICE_NAME}.service"
}

update_app() {
  local branch="main"
  local offline=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      --offline) offline=1; shift ;;
      *) echo "Unbekannte Option: $1" >&2; exit 1 ;;
    esac
  done

  ensure_venv
  if [[ $offline -eq 0 ]]; then
    echo "Hole Updates von Git (Branch ${branch}) ..."

    # If running as root (e.g. via sudo/systemd), run git as SERVICE_USER so
    # the correct SSH keys / agent are used. Otherwise run git as the current user.
    if [[ "$(id -u)" -eq 0 ]]; then
      git_cmd=(sudo -u "${SERVICE_USER}" git)
    else
      git_cmd=(git)
    fi

    "${git_cmd[@]}" -C "${APP_ROOT}" fetch --all
    if [[ -n "$("${git_cmd[@]}" -C "${APP_ROOT}" status --porcelain)" ]]; then
      echo "Arbeitsverzeichnis ist nicht sauber. Bitte committen oder stashen." >&2
      exit 1
    fi
    "${git_cmd[@]}" -C "${APP_ROOT}" checkout "${branch}"
    "${git_cmd[@]}" -C "${APP_ROOT}" pull --ff-only
  else
    echo "Offline-Update: überspringe Git-Fetch."
  fi

  install_deps $([[ $offline -eq 1 ]] && echo --offline || true)
  if [[ -d "${APP_ROOT}/migrations" ]]; then
    echo "Führe Datenbank-Migrationen aus ..."
    FLASK_APP=app "${APP_ROOT}/.venv/bin/flask" db upgrade || true
  fi
  echo "Starte Dienst neu ..."
  require_root
  systemctl restart "${SERVICE_NAME}.service"
  systemctl status --no-pager "${SERVICE_NAME}.service"
}

write_backup() {
  require_root
  ensure_service_user
  write_env_file
  cat > "/etc/systemd/system/${BACKUP_SERVICE_NAME}.service" <<EOF
[Unit]
Description=Kassensystem DB Backup

[Service]
Type=oneshot
EnvironmentFile=${ENV_FILE}
WorkingDirectory=${APP_ROOT}
User=${SERVICE_USER}
Group=${SERVICE_USER}
ExecStart=${APP_ROOT}/scripts/backup_db.sh
EOF

  cat > "/etc/systemd/system/${BACKUP_SERVICE_NAME}.timer" <<EOF
[Unit]
Description=Daily Kassensystem DB Backup

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

  echo "Backup-Unit /etc/systemd/system/${BACKUP_SERVICE_NAME}.service und Timer geschrieben."
}

enable_backup() {
  require_root
  systemctl daemon-reload
  systemctl enable --now "${BACKUP_SERVICE_NAME}.timer"
  systemctl status --no-pager "${BACKUP_SERVICE_NAME}.timer"
}

disable_backup() {
  require_root
  systemctl disable --now "${BACKUP_SERVICE_NAME}.timer"
}

write_kiosk() {
  require_root
  write_env_file
  cat > "/etc/systemd/system/${KIOSK_SERVICE_NAME}.service" <<EOF
[Unit]
Description=Kassensystem Kiosk Mode
After=graphical.target

[Service]
EnvironmentFile=${ENV_FILE}
Environment=DISPLAY=:0
WorkingDirectory=${APP_ROOT}
User=${SUDO_USER:-pi}
ExecStart=${APP_ROOT}/scripts/kiosk_start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
EOF
  echo "Kiosk-Unit /etc/systemd/system/${KIOSK_SERVICE_NAME}.service geschrieben."
}

enable_kiosk() {
  require_root
  systemctl daemon-reload
  systemctl enable --now "${KIOSK_SERVICE_NAME}.service"
  systemctl status --no-pager "${KIOSK_SERVICE_NAME}.service"
}

disable_kiosk() {
  require_root
  systemctl disable --now "${KIOSK_SERVICE_NAME}.service"
}

wifi_add() {
  require_root
  local ssid="$1"
  local pass="$2"

  if [[ -z "${ssid}" || -z "${pass}" ]]; then
    echo "SSID und Passwort erforderlich." >&2
    exit 1
  fi

  if [[ ! -f /etc/wpa_supplicant/wpa_supplicant.conf ]]; then
    cat > /etc/wpa_supplicant/wpa_supplicant.conf <<'EOF'
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=DE
EOF
  fi

  echo "Füge WLAN ${ssid} hinzu ..."
  wpa_passphrase "${ssid}" "${pass}" >> /etc/wpa_supplicant/wpa_supplicant.conf
  wpa_cli -i wlan0 reconfigure || true
}

wifi_up() {
  require_root
  rfkill unblock wifi || true
  ip link set wlan0 up
  wpa_cli -i wlan0 reconfigure || true
  echo "wlan0 aktiviert (sofern vorhanden)."
}

wifi_down() {
  require_root
  ip link set wlan0 down
  echo "wlan0 deaktiviert."
}

show_status() {
  require_root
  systemctl status --no-pager "${SERVICE_NAME}.service"
}

main() {
  local cmd="${1:-}"
case "${cmd}" in
    create-venv) shift; ensure_venv ;;
    install-deps) shift; install_deps "$@" ;;
    write-service) shift; write_service "$@" ;;
    enable-service) shift; enable_service ;;
    disable-service) shift; disable_service ;;
  update) shift; update_app "$@" ;;
  write-backup) shift; write_backup "$@" ;;
  enable-backup) shift; enable_backup "$@" ;;
  disable-backup) shift; disable_backup "$@" ;;
  write-kiosk) shift; write_kiosk "$@" ;;
  enable-kiosk) shift; enable_kiosk "$@" ;;
  disable-kiosk) shift; disable_kiosk "$@" ;;
    wifi-add) shift; wifi_add "${1:-}" "${2:-}" ;;
    wifi-up) shift; wifi_up ;;
    wifi-down) shift; wifi_down ;;
    status) shift; show_status ;;
    -h|--help|"") usage ;;
    *) echo "Unbekannter Befehl: ${cmd}" >&2; usage; exit 1 ;;
  esac
}

main "$@"
