#!/usr/bin/env bash

set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTANCE_DIR="${APP_ROOT}/instance"
DB_PATH="${INSTANCE_DIR}/app.db"
BACKUP_DIR="${BACKUP_DIR:-${APP_ROOT}/instance/backups}"
RETENTION_DAYS="${BACKUP_RETENTION:-14}"
STAMP="$(date +%F_%H%M%S)"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "Keine Datenbank gefunden: ${DB_PATH}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

backup_file="${BACKUP_DIR}/app_${STAMP}.db"
sqlite3 "${DB_PATH}" ".backup '${backup_file}'"

find "${BACKUP_DIR}" -type f -name "app_*.db" -mtime "+${RETENTION_DAYS}" -delete
echo "Backup erstellt: ${backup_file}"
