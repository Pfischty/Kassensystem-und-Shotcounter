#!/usr/bin/env bash

set -euo pipefail

URL="${KIOSK_URL:-http://localhost:8000/cashier}"

if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

if command -v chromium-browser >/dev/null 2>&1; then
  exec chromium-browser --kiosk --incognito --disable-translate --noerrdialogs --disable-infobars "${URL}"
fi

if command -v chromium >/dev/null 2>&1; then
  exec chromium --kiosk --incognito --disable-translate --noerrdialogs --disable-infobars "${URL}"
fi

echo "Chromium nicht gefunden. Bitte chromium oder chromium-browser installieren." >&2
exit 1
