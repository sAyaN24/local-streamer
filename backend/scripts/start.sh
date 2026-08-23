#!/usr/bin/env bash
# Usage: bash scripts/start.sh [device-ip]
#
# Auto-detects the LAN IP if not provided, then:
# 1. Rewrites the LAN IP in .env, livekit.yaml, and docker-compose.yml
# 2. Rebuilds and (re)starts the full Docker stack
# 3. Waits for the seed service to finish (demo-room ready)
# 4. Activates the Python venv and starts the dummy video publisher

set -euo pipefail

# ── IP detection ──────────────────────────────────────────────────────────────
detect_lan_ip() {
  local ip=""

  # macOS: use the interface that owns the default route
  if command -v route &>/dev/null && [[ "$(uname)" == "Darwin" ]]; then
    local iface
    iface=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')
    if [[ -n "$iface" ]]; then
      ip=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
    fi
  fi

  # Linux fallback: hostname -I gives space-separated IPs; take first non-loopback
  if [[ -z "$ip" ]] && command -v hostname &>/dev/null; then
    ip=$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i !~ /^127\./) {print $i; exit}}')
  fi

  # Last resort: parse ifconfig/ip addr
  if [[ -z "$ip" ]] && command -v ip &>/dev/null; then
    ip=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/{print $7; exit}')
  fi

  echo "$ip"
}

if [[ $# -ge 1 ]]; then
  IP="$1"
else
  echo "==> Auto-detecting LAN IP..."
  IP=$(detect_lan_ip)
  if [[ -z "$IP" ]]; then
    echo "Error: could not auto-detect LAN IP. Pass it explicitly:"
    echo "  bash scripts/start.sh 192.168.1.5"
    exit 1
  fi
  echo "    Detected: $IP"
fi

# Basic IP format check
if ! [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: '$IP' does not look like a valid IPv4 address."
  exit 1
fi

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
LIVEKIT_YAML="$BACKEND_DIR/docker/livekit.yaml"
COMPOSE_FILE="$BACKEND_DIR/docker-compose.yml"
VIDEO="$SCRIPT_DIR/../../../Vision/210526-1254.mp4"
VENV="$BACKEND_DIR/.venv"

# ── 1. Update IP in config files ──────────────────────────────────────────────
echo "==> Updating IP to $IP in config files..."

# .env  →  LIVEKIT_URL=ws://<IP>:7880
sed -i.bak "s|LIVEKIT_URL=ws://[^:]*:7880|LIVEKIT_URL=ws://$IP:7880|" "$ENV_FILE"
echo "    .env updated"

# livekit.yaml  →  node_ip: <IP>
sed -i.bak "s|node_ip:.*|node_ip: $IP|" "$LIVEKIT_YAML"
echo "    docker/livekit.yaml updated"

# docker-compose.yml  →  VITE_API_BASE_URL default
sed -i.bak "s|VITE_API_BASE_URL:-http://[^:]*:8000|VITE_API_BASE_URL:-http://$IP:8000|" "$COMPOSE_FILE"
echo "    docker-compose.yml updated"

# Clean up sed backups
rm -f "$ENV_FILE.bak" "$LIVEKIT_YAML.bak" "$COMPOSE_FILE.bak"

# ── 2. Rebuild and start Docker stack ────────────────────────────────────────
echo ""
echo "==> Rebuilding and starting Docker stack..."
cd "$BACKEND_DIR"
docker compose down --remove-orphans
VITE_API_BASE_URL="http://$IP:8000" docker compose up --build -d

# ── 3. Wait for seed service to finish (demo-room ready) ─────────────────────
echo ""
echo "==> Waiting for seed service to finish seeding demo-room..."
SEED_TIMEOUT=120
ELAPSED=0
while true; do
  STATUS=$(docker inspect --format '{{.State.Status}}' streammark-seed 2>/dev/null || echo "missing")
  EXIT_CODE=$(docker inspect --format '{{.State.ExitCode}}' streammark-seed 2>/dev/null || echo "1")

  if [[ "$STATUS" == "exited" && "$EXIT_CODE" == "0" ]]; then
    echo "    Seed complete."
    break
  elif [[ "$STATUS" == "exited" && "$EXIT_CODE" != "0" ]]; then
    echo "Error: seed service exited with code $EXIT_CODE. Check logs:"
    docker logs streammark-seed
    exit 1
  fi

  if [[ $ELAPSED -ge $SEED_TIMEOUT ]]; then
    echo "Error: timed out waiting for seed service after ${SEED_TIMEOUT}s."
    docker logs streammark-seed
    exit 1
  fi

  sleep 3
  ELAPSED=$((ELAPSED + 3))
  echo "    Still waiting... (${ELAPSED}s)"
done

# ── 4. Set up Python venv ─────────────────────────────────────────────────────
echo ""
echo "==> Setting up Python environment..."
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
  echo "    venv created."
fi

source "$VENV/bin/activate"

if ! python -c "import streammark" 2>/dev/null; then
  echo "    Installing streammark package..."
  pip install -e "$BACKEND_DIR/.[dev]" --quiet
fi

# ── 5. Start dummy publisher ──────────────────────────────────────────────────
echo ""
echo "==> Stack is up. Services:"
echo "    LiveKit  ws://$IP:7880"
echo "    API      http://$IP:8000"
echo "    Frontend http://$IP:5173"
echo ""

if [[ ! -f "$VIDEO" ]]; then
  echo "Warning: video not found at: $VIDEO"
  echo "Skipping publisher. Run manually:"
  echo "  python scripts/dummy_publisher.py --room demo-room --video <path>"
  exit 0
fi

echo "==> Starting dummy publisher (Ctrl+C to stop)..."
python "$SCRIPT_DIR/dummy_publisher.py" \
  --room demo-room \
  --video "$VIDEO"
