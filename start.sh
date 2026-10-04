#!/usr/bin/env bash
# Start OmniTag Mall so phones on the same network (e.g. your phone's hotspot) can open it.
# Detects this laptop's network address, uses it for QR codes, and creates an admin password on first run.
set -euo pipefail
cd "$(dirname "$0")"

PORT=8000
IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}')
if [ -z "${IP:-}" ]; then
  IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ -z "${IP:-}" ]; then
  echo "Could not detect a network address. Connect to Wi-Fi or your phone's hotspot first." >&2
  exit 1
fi

# First run: create .env with a random admin password
if [ ! -f .env ] || ! grep -q '^ADMIN_PASSWORD=' .env; then
  PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(9))")
  echo "ADMIN_PASSWORD=$PASS" >> .env
  chmod 600 .env
  echo "Created .env with a new admin password."
fi

export PUBLIC_URL="http://$IP:$PORT"
docker compose up -d

echo
echo "OmniTag Mall is starting:"
echo "  Shoppers (phones on this network): $PUBLIC_URL"
echo "  This laptop:                       http://localhost:$PORT"
echo "  Admin:                             $PUBLIC_URL/admin   (password: see ADMIN_PASSWORD in .env)"
echo
echo "QR price tags use $PUBLIC_URL. If this address changes (e.g. after reconnecting"
echo "to the hotspot), run ./start.sh again and reprint the tags from Admin > QR price tags."
