#!/usr/bin/env bash
# Usage: bash scripts/start_live.sh [device-ip] [capture-device-override]
#
# Auto-detects the LAN IP if not provided, then:
# 1. Rewrites the LAN IP in .env, livekit.yaml, and docker-compose.yml
# 2. Rebuilds and (re)starts the full Docker stack (frontend + backend)
# 3. Waits for the seed service to finish (demo-room ready)
# 4. Activates the Python venv
# 5. Auto-detects the live capture card (or uses the second arg as an override)
# 6. Publishes it into demo-room via the real streammark-ingest pipeline

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

  # Windows (Git Bash/MSYS has no hostname -I or ip route): parse ipconfig,
  # skipping APIPA (169.254.x.x) and loopback. First match wins, which in
  # practice is the physical Wi-Fi/Ethernet adapter listed before Hyper-V/WSL
  # virtual switches.
  if [[ -z "$ip" ]] && command -v ipconfig &>/dev/null; then
    ip=$(ipconfig | grep -A0 "IPv4 Address" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | grep -v '^169\.254\.' | grep -v '^127\.' | head -1)
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
    echo "  bash scripts/start_live.sh 192.168.1.5"
    exit 1
  fi
  echo "    Detected: $IP"
fi

if ! [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: '$IP' does not look like a valid IPv4 address."
  exit 1
fi

CAPTURE_OVERRIDE="${2:-}"

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
LIVEKIT_YAML="$BACKEND_DIR/docker/livekit.yaml"
COMPOSE_FILE="$BACKEND_DIR/docker-compose.yml"
VENV="$BACKEND_DIR/.venv"

# ── 1. Update IP in config files ──────────────────────────────────────────────
echo "==> Updating IP to $IP in config files..."
sed -i.bak "s|LIVEKIT_URL=ws://[^:]*:7880|LIVEKIT_URL=ws://$IP:7880|" "$ENV_FILE"
echo "    .env updated"
sed -i.bak "s|node_ip:.*|node_ip: $IP|" "$LIVEKIT_YAML"
echo "    docker/livekit.yaml updated"
sed -i.bak "s|VITE_API_BASE_URL:-http://[^:]*:8000|VITE_API_BASE_URL:-http://$IP:8000|" "$COMPOSE_FILE"
echo "    docker-compose.yml updated"
rm -f "$ENV_FILE.bak" "$LIVEKIT_YAML.bak" "$COMPOSE_FILE.bak"

# ── 2. Rebuild and start Docker stack (frontend + backend) ───────────────────
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
  python -m venv "$VENV"
  echo "    venv created."
fi

if [[ -f "$VENV/bin/activate" ]]; then
  source "$VENV/bin/activate"
elif [[ -f "$VENV/Scripts/activate" ]]; then
  source "$VENV/Scripts/activate"
else
  echo "Error: could not find venv activate script under $VENV/bin or $VENV/Scripts."
  exit 1
fi

if ! python -c "import streammark" 2>/dev/null; then
  echo "    Installing streammark package..."
  pip install -e ".[dev]" --quiet
fi

echo ""
echo "==> Stack is up. Services:"
echo "    LiveKit  ws://$IP:7880"
echo "    API      http://$IP:8000"
echo "    Frontend http://$IP:5173"

# ── 5. Detect capture card ────────────────────────────────────────────────────
# A short grace pause: if a previous ingest process was just killed, some cheap
# capture-card chipsets need a moment to release their DirectShow/V4L2 handle
# before they'll accept a new open() call.
sleep 2

echo ""
if [[ -n "$CAPTURE_OVERRIDE" ]]; then
  DEVICE="$CAPTURE_OVERRIDE"
  echo "==> Using capture device override: $DEVICE"
else
  echo "==> Auto-detecting capture card..."
  DEVICE=$(python "$SCRIPT_DIR/detect_capture_device.py")
  echo "    Detected capture device: $DEVICE"
fi

# ── 6. Start the real ingest publisher into demo-room ─────────────────────────
echo ""
echo "==> Starting streammark-ingest (Ctrl+C to stop)..."
streammark-ingest --room demo-room --device "$DEVICE" --width 1920 --height 1080 --fps 30
