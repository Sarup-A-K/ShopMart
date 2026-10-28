#!/usr/bin/env bash
# Start ShopMart so phones can open it.
#   ./start.sh            phones on the same network (e.g. your phone's hotspot) use this laptop's address
#   ./start.sh --tunnel   also opens a public https:// address through a Cloudflare tunnel, so any phone on
#                         any network can open it (and the in-page camera scanner works). With CLOUDFLARE_TUNNEL_TOKEN and
#                         PUBLIC_HOSTNAME in .env it uses your own fixed address (e.g. shop.yourdomain.com); otherwise a
#                         random temporary one. Stop it with `docker rm -f omnitag_tunnel` when you are done: while it
#                         runs, anyone with the link can use the site.
#   ./start.sh --serveo [name]   a free SSH tunnel with a name you choose: https://<name>.serveo.net (default name: shopmart).
#                         Needs the name to be free and the service to be up. Stop it with `./start.sh --stop-serveo`.
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

if [ "${1:-}" = "--stop-serveo" ]; then
  [ -f .serveo.pid ] && kill "$(cat .serveo.pid)" 2>/dev/null || true
  rm -f .serveo.pid .serveo.log
  echo "Serveo tunnel stopped."
  exit 0
fi

if [ "${1:-}" = "--serveo" ]; then
  NAME="${2:-shopmart}"
  [ -f .serveo.pid ] && kill "$(cat .serveo.pid)" 2>/dev/null || true
  : > .serveo.log
  nohup ssh -tt -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
    -R "$NAME:80:localhost:$PORT" serveo.net > .serveo.log 2>&1 &
  echo $! > .serveo.pid
  echo "Opening https://$NAME.serveo.net ..."
  for _ in $(seq 1 15); do
    grep -q "Forwarding HTTP traffic from" .serveo.log 2>/dev/null && break
    sleep 2
  done
  if grep -q "Forwarding HTTP traffic from" .serveo.log; then
    export PUBLIC_URL=$(grep -o 'https://[A-Za-z0-9.-]*serveo[A-Za-z0-9.-]*' .serveo.log | head -1)
  else
    echo "Serveo did not open the tunnel. Its message was:" >&2
    sed 's/\x1b\[[0-9;]*[A-Za-z]//g' .serveo.log | head -8 >&2
    kill "$(cat .serveo.pid)" 2>/dev/null || true; rm -f .serveo.pid
  fi
fi

if [ "${1:-}" = "--tunnel" ]; then
  # Read two optional settings from .env without executing it
  env_value() { { grep -m1 "^$1=" .env 2>/dev/null || true; } | cut -d= -f2- | tr -d '"'"'"'\r' | sed 's/^ *//;s/ *$//'; }
  TUNNEL_TOKEN_VALUE=$(env_value CLOUDFLARE_TUNNEL_TOKEN)
  PUBLIC_HOST=$(env_value PUBLIC_HOSTNAME | sed 's#^https\?://##; s#/.*$##')

  docker rm -f omnitag_tunnel >/dev/null 2>&1 || true
  start_tunnel() {   # $1: extra cloudflared flags (quick tunnel only)
    docker rm -f omnitag_tunnel >/dev/null 2>&1 || true
    if [ -n "$TUNNEL_TOKEN_VALUE" ] && [ -n "$PUBLIC_HOST" ]; then
      # Named tunnel on your own domain: the address never changes. The token is passed as an
      # environment variable so it does not appear in the process list.
      TUNNEL_TOKEN="$TUNNEL_TOKEN_VALUE" docker run -d --name omnitag_tunnel --network host -e TUNNEL_TOKEN \
        cloudflare/cloudflared:latest tunnel --no-autoupdate $1 run >/dev/null
    else
      docker run -d --name omnitag_tunnel --network host cloudflare/cloudflared:latest \
        tunnel --no-autoupdate $1 --url "http://localhost:$PORT" >/dev/null
    fi
    for _ in $(seq 1 25); do
      docker logs omnitag_tunnel 2>&1 | grep -q "Registered tunnel connection" && return 0
      sleep 2
    done
    return 1
  }
  if [ -n "$TUNNEL_TOKEN_VALUE" ] && [ -n "$PUBLIC_HOST" ]; then
    echo "Opening your tunnel at https://$PUBLIC_HOST (about 20 seconds)..."
  else
    echo "Opening a temporary public tunnel with a random address (about 20 seconds)..."
    echo "(To get a fixed address on your own domain, set CLOUDFLARE_TUNNEL_TOKEN and PUBLIC_HOSTNAME in .env; see README.)"
  fi
  if ! start_tunnel "" && ! start_tunnel "--protocol http2"; then
    echo "Could not open the tunnel (the network may block it). Continuing with the local address only." >&2
    docker rm -f omnitag_tunnel >/dev/null 2>&1 || true
  elif [ -n "$TUNNEL_TOKEN_VALUE" ] && [ -n "$PUBLIC_HOST" ]; then
    export PUBLIC_URL="https://$PUBLIC_HOST"
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
