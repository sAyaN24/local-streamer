#!/usr/bin/env bash
# Usage: bash scripts/start_capture.sh [device-ip] [capture-device-override]
#
# Full-stack launcher for LIVE CAPTURE-CARD input (no dummy video anywhere).
# Standalone sibling of start.sh/start_live.sh; it does not source or modify them.
#
# 1. Resolves a working docker compose invocation (plugin or standalone binary)
# 2. Rewrites the LAN IP in .env, livekit.yaml, and docker-compose.yml
# 3. Rebuilds and (re)starts the Docker stack, explicitly WITHOUT the dummy publisher
# 4. Waits for the seed service to finish (demo-room ready)
# 5. Finds a Python >=3.12 interpreter and prepares the venv
# 6. Detects the capture card (V4L2 on Linux, AVFoundation index on macOS, DirectShow on Windows)
# 7. Pre-flights the device: verifies it opens AND yields non-black frames before streaming
# 8. Starts the real streammark-ingest publisher into demo-room

set -euo pipefail

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
LIVEKIT_YAML="$BACKEND_DIR/docker/livekit.yaml"
COMPOSE_FILE="$BACKEND_DIR/docker-compose.yml"
VENV="$BACKEND_DIR/.venv"

ROOM="${ROOM:-demo-room}"
CAP_WIDTH="${CAP_WIDTH:-1920}"
CAP_HEIGHT="${CAP_HEIGHT:-1080}"
CAP_FPS="${CAP_FPS:-30}"

# ── 0. Resolve docker compose ─────────────────────────────────────────────────
# Docker Desktop ships compose as a CLI plugin, but a Homebrew-installed docker
# client often has only the standalone `docker-compose` binary. Support both
# instead of assuming the plugin exists.
if docker compose version &>/dev/null; then
  COMPOSE=(docker compose)
elif command -v docker-compose &>/dev/null; then
  COMPOSE=(docker-compose)
else
  echo "Error: neither 'docker compose' nor 'docker-compose' is available."
  echo "Install Docker Compose, or symlink an existing binary into the plugin dir:"
  echo "  mkdir -p ~/.docker/cli-plugins"
  echo "  ln -sf \"\$(command -v docker-compose)\" ~/.docker/cli-plugins/docker-compose"
  exit 1
fi

if ! docker info &>/dev/null; then
  echo "Error: the Docker daemon is not reachable. Start Docker Desktop and retry."
  exit 1
fi

# ── IP detection ──────────────────────────────────────────────────────────────
detect_lan_ip() {
  local ip=""

  if command -v route &>/dev/null && [[ "$(uname)" == "Darwin" ]]; then
    local iface
    iface=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')
    if [[ -n "$iface" ]]; then
      ip=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
    fi
  fi

  if [[ -z "$ip" ]] && command -v hostname &>/dev/null; then
    ip=$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i !~ /^127\./) {print $i; exit}}')
  fi

  if [[ -z "$ip" ]] && command -v ip &>/dev/null; then
    ip=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/{print $7; exit}')
  fi

  echo "$ip"
}

if [[ $# -ge 1 && -n "${1:-}" ]]; then
  IP="$1"
else
  echo "==> Auto-detecting LAN IP..."
  IP=$(detect_lan_ip)
  if [[ -z "$IP" ]]; then
    echo "Error: could not auto-detect LAN IP. Pass it explicitly:"
    echo "  bash scripts/start_capture.sh 192.168.1.5"
    exit 1
  fi
  echo "    Detected: $IP"
fi

if ! [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: '$IP' does not look like a valid IPv4 address."
  exit 1
fi

CAPTURE_OVERRIDE="${2:-}"

# ── 1. Update IP in config files ──────────────────────────────────────────────
echo ""
echo "==> Updating IP to $IP in config files..."
sed -i.bak "s|LIVEKIT_URL=ws://[^:]*:7880|LIVEKIT_URL=ws://$IP:7880|" "$ENV_FILE"
sed -i.bak "s|node_ip:.*|node_ip: $IP|" "$LIVEKIT_YAML"
sed -i.bak "s|VITE_API_BASE_URL:-http://[^:]*:8000|VITE_API_BASE_URL:-http://$IP:8000|" "$COMPOSE_FILE"
rm -f "$ENV_FILE.bak" "$LIVEKIT_YAML.bak" "$COMPOSE_FILE.bak"
echo "    .env, docker/livekit.yaml, docker-compose.yml updated"

# ── 2. Rebuild and start the stack (live services only) ───────────────────────
# The 'demo' profile is deliberately NOT passed: dummy-publisher only starts when
# that profile is requested, so a plain `up` gives a stack with no synthetic video.
# The explicit `down` also tears down a dummy-publisher left running by start.sh.
echo ""
echo "==> Stopping any existing stack (including a leftover dummy publisher)..."
cd "$BACKEND_DIR"
"${COMPOSE[@]}" --profile demo down --remove-orphans

echo ""
echo "==> Rebuilding and starting Docker stack (live capture mode, no dummy video)..."
VITE_API_BASE_URL="http://$IP:8000" "${COMPOSE[@]}" up --build -d livekit mongo api frontend seed

# ── 3. Wait for seed service to finish ────────────────────────────────────────
echo ""
echo "==> Waiting for seed service to finish seeding '$ROOM'..."
SEED_TIMEOUT=180
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

echo ""
echo "==> Stack is up. Services:"
echo "    LiveKit  ws://$IP:7880"
echo "    API      http://$IP:8000"
echo "    Frontend http://$IP:5173/room/$ROOM"

# ── 4. Python environment ─────────────────────────────────────────────────────
# streammark-ingest MUST run natively, not in a container: Docker Desktop on
# macOS/Windows cannot pass a USB capture device through to a container, and the
# ingest process needs direct access to the card. pyproject.toml requires >=3.12,
# so an older default `python3` (e.g. Apple's system 3.9) cannot be used here.
echo ""
echo "==> Preparing Python environment (needs >=3.12)..."

find_python() {
  local candidate
  for candidate in python3.14 python3.13 python3.12 python3 python; do
    command -v "$candidate" &>/dev/null || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

venv_python() {
  if [[ -x "$VENV/bin/python" ]]; then
    echo "$VENV/bin/python"
  elif [[ -x "$VENV/Scripts/python.exe" ]]; then
    echo "$VENV/Scripts/python.exe"
  fi
}

# Reuse the venv only if it is already on a new enough interpreter; a venv built
# by an older sibling script against Python 3.9 would fail the install below with
# a confusing pip error rather than an obvious version error.
VPY="$(venv_python)"
if [[ -n "$VPY" ]] && ! "$VPY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
  echo "    Existing venv uses $("$VPY" --version 2>&1) which is too old; recreating."
  rm -rf "$VENV"
  VPY=""
fi

if [[ -z "$VPY" ]]; then
  if ! BASE_PY="$(find_python)"; then
    echo ""
    echo "Error: no Python >=3.12 found on PATH, but this project requires it"
    echo "       (pyproject.toml: requires-python = \">=3.12\")."
    echo ""
    echo "  Detected default: $(python3 --version 2>&1 || echo 'none')"
    echo ""
    echo "  The Docker stack above is running and usable, but live capture cannot"
    echo "  start without a native Python >=3.12 -- a container cannot reach the"
    echo "  capture card on macOS or Windows."
    echo ""
    echo "  Install one, then re-run this script:"
    echo "    macOS   brew install python@3.12"
    echo "    Ubuntu  sudo apt install python3.12 python3.12-venv"
    echo "    Windows winget install Python.Python.3.12"
    exit 1
  fi
  echo "    Using $BASE_PY ($("$BASE_PY" --version 2>&1))"
  "$BASE_PY" -m venv "$VENV"
  VPY="$(venv_python)"
fi

"$VPY" -m pip install --upgrade pip --quiet
if ! "$VPY" -c "import streammark" 2>/dev/null; then
  echo "    Installing streammark package..."
  "$VPY" -m pip install -e "$BACKEND_DIR/.[dev]" --quiet
fi

VENV_BIN="$(dirname "$VPY")"
export PATH="$VENV_BIN:$PATH"

# ── 5. Detect the capture card ────────────────────────────────────────────────
# Grace pause: cheap capture chipsets need a moment to release their
# DirectShow/V4L2 handle after a previous ingest process was killed.
sleep 2

echo ""
if [[ -n "$CAPTURE_OVERRIDE" ]]; then
  DEVICE="$CAPTURE_OVERRIDE"
  echo "==> Using capture device override: $DEVICE"
else
  echo "==> Auto-detecting capture card..."
  # scripts/detect_capture_device.py probes /dev/video* on any non-Windows host,
  # which finds nothing on macOS (AVFoundation exposes integer indices, not
  # device nodes). Try it first, then fall back to an index probe on macOS.
  DEVICE="$("$VPY" "$SCRIPT_DIR/detect_capture_device.py" 2>/dev/null || true)"

  if [[ -z "$DEVICE" && "$(uname)" == "Darwin" ]]; then
    echo "    No /dev/video* nodes (expected on macOS); probing AVFoundation indices..."
    DEVICE="$("$VPY" - <<'PY' || true
import contextlib, io, sys
import cv2

# Index 0 is nearly always the built-in FaceTime camera, so prefer the highest
# index that both opens and yields a readable frame -- an external capture card
# enumerates after the internal camera on macOS.
found = []
for i in range(6):
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
        ok = cap.isOpened() and cap.read()[0]
        cap.release()
    print(f"  index {i}: readable={ok}", file=sys.stderr)
    if ok:
        found.append(i)

if found:
    print(found[-1])
PY
)"
  fi

  if [[ -z "$DEVICE" ]]; then
    echo ""
    echo "Error: no readable capture device found."
    echo "  - Confirm the capture card is plugged in and not held by OBS/QuickTime/Zoom."
    if [[ "$(uname)" == "Darwin" ]]; then
      echo "  - macOS gates camera access: grant your terminal permission under"
      echo "    System Settings > Privacy & Security > Camera, then re-run."
    fi
    echo "  - Or pass the device explicitly:"
    echo "      bash scripts/start_capture.sh $IP /dev/video0   # Linux"
    echo "      bash scripts/start_capture.sh $IP 1             # macOS/Windows index"
    exit 1
  fi
  echo "    Detected capture device: $DEVICE"
fi

# ── 6. Pre-flight the device ──────────────────────────────────────────────────
# An open device is NOT proof of a usable feed. Interlaced sources (common on
# capture cards, e.g. AverMedia in 1080i) make OpenCV's swscaler fail per frame
# and hand back an all-zero buffer while read() still reports success -- the
# feed then streams pure black with no error anywhere in the stack. Catch that
# here, loudly, instead of after someone reports "the video is blank".
echo ""
echo "==> Pre-flighting capture device (open + non-black frame check)..."
set +e
"$VPY" - "$DEVICE" "$CAP_WIDTH" "$CAP_HEIGHT" "$CAP_FPS" <<'PY'
import sys
import cv2

raw, want_w, want_h, want_fps = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
dev = int(raw) if raw.isdigit() else raw

if sys.platform == "darwin":
    backend = cv2.CAP_AVFOUNDATION
elif sys.platform == "win32":
    backend = cv2.CAP_DSHOW
else:
    backend = cv2.CAP_V4L2

cap = cv2.VideoCapture(dev, backend)
if not cap.isOpened():
    print(f"    FAIL: could not open {raw!r}")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, want_w)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, want_h)
cap.set(cv2.CAP_PROP_FPS, want_fps)

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)
print(f"    device={raw} negotiated={w}x{h} @ {fps:.0f}fps (requested {want_w}x{want_h} @ {want_fps})")
if (w, h) != (want_w, want_h):
    print("    NOTE: device did not honor the requested resolution; it will stream what it negotiated.")

# Discard a few warm-up frames: many cards emit blank frames right after open.
for _ in range(5):
    cap.read()

blank = 0
read_fail = 0
peak = 0
for _ in range(15):
    ok, frame = cap.read()
    if not ok or frame is None:
        read_fail += 1
        continue
    m = int(frame.max())
    peak = max(peak, m)
    if m == 0:
        blank += 1
cap.release()

print(f"    sampled 15 frames: read_failures={read_fail} all_black={blank} peak_pixel={peak}")

if read_fail == 15:
    print("    FAIL: device opened but returned no frames.")
    sys.exit(1)
if peak == 0:
    print("")
    print("    FAIL: every sampled frame was pure black (peak pixel value 0).")
    print("    This is the classic interlaced-source failure: OpenCV cannot")
    print("    deinterlace, so sws_scale returns a zeroed buffer while read()")
    print("    still reports success. Streaming would produce a blank feed.")
    print("    Fixes: set the source device to a PROGRESSIVE mode (1080p, not")
    print("    1080i), or put a deinterlace stage in front of the capture.")
    sys.exit(2)

print("    OK: live frames contain real picture data.")
PY
PREFLIGHT=$?
set -e

if [[ $PREFLIGHT -ne 0 ]]; then
  echo ""
  echo "Aborting before publish: the capture device would stream an unusable feed."
  echo "The Docker stack is still running -- fix the device and re-run this script,"
  echo "or stop the stack with: ${COMPOSE[*]} --profile demo down"
  exit 1
fi

# ── 7. Start the live ingest publisher ────────────────────────────────────────
echo ""
echo "==> Starting streammark-ingest from capture device '$DEVICE' (Ctrl+C to stop)..."
echo "    Watch at: http://$IP:5173/room/$ROOM"
echo ""
exec streammark-ingest \
  --room "$ROOM" \
  --device "$DEVICE" \
  --width "$CAP_WIDTH" \
  --height "$CAP_HEIGHT" \
  --fps "$CAP_FPS"
