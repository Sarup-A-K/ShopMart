#!/usr/bin/env bash
# Start ShopMart so phones can open it.
#   ./start.sh            phones on the same network (e.g. your phone's hotspot) use this laptop's address
#   ./start.sh --tunnel   also opens a public https:// address through a free Cloudflare tunnel, so any phone on
#                         any network can open it (and the in-page camera scanner works). Stop it with
#                         `docker rm -f omnitag_tunnel` when you are done: while it runs, anyone with the link can use the site.
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

if [ "${1:-}" = "--tunnel" ]; then
  docker rm -f omnitag_tunnel >/dev/null 2>&1 || true
  start_tunnel() {   # $1: extra cloudflared flags
    docker rm -f omnitag_tunnel >/dev/null 2>&1 || true
    docker run -d --name omnitag_tunnel --network host cloudflare/cloudflared:latest \
      tunnel --no-autoupdate $1 --url "http://localhost:$PORT" >/dev/null
    for _ in $(seq 1 25); do
      docker logs omnitag_tunnel 2>&1 | grep -q "Registered tunnel connection" && return 0
      sleep 2
    done
    return 1
  }
  echo "Opening the public tunnel (about 20 seconds)..."
  if ! start_tunnel "" && ! start_tunnel "--protocol http2"; then
    echo "Could not open the tunnel (the network may block it). Continuing with the local address only." >&2
    docker rm -f omnitag_tunnel >/dev/null 2>&1 || true
  else
    TUNNEL_URL=$(docker logs omnitag_tunnel 2>&1 | grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' | head -1)
    [ -n "$TUNNEL_URL" ] && export PUBLIC_URL="$TUNNEL_URL"
  fi
fi

docker compose up -d

echo
echo "ShopMart is starting:"
echo "  Shoppers (phones): $PUBLIC_URL"
if [ "$PUBLIC_URL" != "http://$IP:$PORT" ]; then echo "  Same Wi-Fi/hotspot only:           http://$IP:$PORT"; fi
echo "  This laptop:                       http://localhost:$PORT"
echo "  Admin:                             $PUBLIC_URL/admin   (password: see ADMIN_PASSWORD in .env)"
echo
echo "QR price tags use $PUBLIC_URL. If this address changes (e.g. after reconnecting"
echo "to the hotspot), run ./start.sh again and reprint the tags from Admin > QR price tags."
