#!/usr/bin/env bash

set -euo pipefail

APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="${APP_ROOT}/deploy/kassensystem-update.service"
UNIT_DST="/etc/systemd/system/kassensystem-update.service"
SUDOERS_DST="/etc/sudoers.d/kassensystem-update"

if [[ $(id -u) -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

if [[ ! -f "${UNIT_SRC}" ]]; then
  echo "Unit template not found: ${UNIT_SRC}" >&2
  exit 1
fi

echo "Installing systemd unit to ${UNIT_DST}..."
cp "${UNIT_SRC}" "${UNIT_DST}"
chmod 644 "${UNIT_DST}"

echo "Reloading systemd and enabling unit..."
systemctl daemon-reload
systemctl enable --now kassensystem-update.service

echo "Writing sudoers snippet to allow 'kassensystem' to start the unit..."
cat > "${SUDOERS_DST}" <<'EOF'
# Allow the service user to start and check the update unit without a password
kassensystem ALL=(root) NOPASSWD: /bin/systemctl start kassensystem-update.service, /bin/systemctl status kassensystem-update.service
EOF
chmod 440 "${SUDOERS_DST}"

echo "Installation complete."
echo "If the web service runs with NoNewPrivileges=true, you may still need to set NoNewPrivileges=false for the web unit or restart the service."

echo "Test by running (as non-root):"
echo "  sudo -u kassensystem systemctl start kassensystem-update.service"
echo "Or trigger from web UI and then check journal:"
echo "  sudo journalctl -u kassensystem-update.service --no-pager"
