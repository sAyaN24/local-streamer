#!/usr/bin/env bash
# Usage: bash scripts/start_webcam.sh [device-ip] [webcam-device-override]
#
# Full-stack launcher for a WEBCAM source (built-in or plain USB camera).
# Standalone sibling of start.sh/start_live.sh/start_capture.sh; it does not
# source or modify them.
#
# Same flow as start_capture.sh, but the device detection is inverted: an HDMI
# capture card enumerates *after* the built-in camera, so start_capture.sh
# prefers the highest working index. Here the built-in/USB webcam is the target,
# so name hints pick a webcam-like device and ties fall back to the LOWEST index.
#
# 1. Resolves a working docker compose invocation (plugin or standalone binary)
# 2. Rewrites the LAN IP in .env, livekit.yaml, and docker-compose.yml
# 3. Rebuilds and (re)starts the Docker stack, explicitly WITHOUT the dummy publisher
# 4. Waits for the seed service to finish (demo-room ready)
# 5. Finds a Python >=3.12 interpreter and prepares the venv
# 6. Detects the webcam (V4L2 on Linux, AVFoundation index on macOS, DirectShow on Windows)
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
# Webcams negotiate 720p far more reliably than 1080p, and most cap out at 30fps
# there; the device keeps whatever it actually negotiates either way.
CAP_WIDTH="${CAP_WIDTH:-1280}"
CAP_HEIGHT="${CAP_HEIGHT:-720}"
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
    echo "  bash scripts/start_webcam.sh 192.168.1.5"
    exit 1
  fi
  echo "    Detected: $IP"
fi

if ! [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: '$IP' does not look like a valid IPv4 address."
  exit 1
fi

WEBCAM_OVERRIDE="${2:-}"

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
echo "==> Rebuilding and starting Docker stack (webcam mode, no dummy video)..."
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
# macOS/Windows cannot pass a USB/built-in camera through to a container, and the
# ingest process needs direct access to it. pyproject.toml requires >=3.12, so an
# older default `python3` (e.g. Apple's system 3.9) cannot be used here.
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
    echo "  The Docker stack above is running and usable, but webcam capture cannot"
    echo "  start without a native Python >=3.12 -- a container cannot reach the"
    echo "  camera on macOS or Windows."
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

# ── 5. Detect the webcam ──────────────────────────────────────────────────────
# Grace pause: a camera can need a moment to release its DirectShow/V4L2/
# AVFoundation handle after a previous ingest process was killed.
sleep 2

echo ""
if [[ -n "$WEBCAM_OVERRIDE" ]]; then
  DEVICE="$WEBCAM_OVERRIDE"
  echo "==> Using webcam device override: $DEVICE"
else
  echo "==> Auto-detecting webcam..."
  # Deliberately NOT scripts/detect_capture_device.py: that one is tuned to find
  # an external capture card (highest index / capture-card name hints), which is
  # the opposite preference from what we want here.
  DEVICE="$("$VPY" - <<'PY' || true
import contextlib
import glob
import io
import sys

import cv2

# Name fragments that mark a device as a webcam vs. an HDMI capture dongle. On
# Windows the DirectShow friendly name is available via pygrabber, so prefer a
# webcam-looking device over a capture card outright; elsewhere only the index
# ordering is available and the lowest working device wins.
WEBCAM_HINTS = (
    "integrated", "built-in", "built in", "internal camera", "facetime",
    "laptop camera", "front camera", "user-facing", "truevision", "webcam", "camera",
)
CAPTURE_HINTS = (
    "capture", "hdmi", "avermedia", "elgato", "cam link", "startech", "ezcap",
    "video grabber", "grabber", "acasis", "ugreen",
)


def score(name):
    if not name:
        return 0
    low = name.lower()
    s = 0
    if any(h in low for h in WEBCAM_HINTS):
        s += 2
    if any(h in low for h in CAPTURE_HINTS):
        s -= 2
    return s


def dshow_names():
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        print("  (pygrabber not installed; falling back to lowest-index guess)", file=sys.stderr)
        return None
    try:
        return FilterGraph().get_input_devices()
    except Exception as exc:
        print(f"  (could not enumerate DirectShow names: {exc})", file=sys.stderr)
        return None


def readable(dev, backend):
    # OpenCV chatters on stderr for every index it fails to open; swallow that so
    # the probe log stays readable.
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        cap = cv2.VideoCapture(dev, backend)
        ok = cap.isOpened() and cap.read()[0]
        cap.release()
    return ok


if sys.platform == "win32":
    names = dshow_names()
    found = []
    for i in range(10):
        ok = readable(i, cv2.CAP_DSHOW)
        name = names[i] if names and i < len(names) else None
        print(f"  index {i}{f' ({name})' if name else ''}: readable={ok}", file=sys.stderr)
        if ok:
            found.append(i)
    # Best name score wins; ties go to the LOWEST index (built-in camera first).
    chosen = min(found, key=lambda i: (-score(names[i] if names and i < len(names) else None), i)) if found else None
elif sys.platform == "darwin":
    # macOS has no /dev/video* nodes; AVFoundation exposes integer indices, and
    # index 0 is nearly always the built-in FaceTime camera.
    found = [i for i in range(6) if readable(i, cv2.CAP_AVFOUNDATION)]
    for i in found:
        print(f"  index {i}: readable=True", file=sys.stderr)
    chosen = found[0] if found else None
else:
    found = [p for p in sorted(glob.glob("/dev/video*")) if readable(p, cv2.CAP_V4L2)]
    for p in found:
        print(f"  {p}: readable=True", file=sys.stderr)
    chosen = found[0] if found else None

print(f"Candidates: {found} -> chosen: {chosen}", file=sys.stderr)
if chosen is not None:
    print(chosen)
PY
)"

  if [[ -z "$DEVICE" ]]; then
    echo ""
    echo "Error: no readable webcam found."
    echo "  - Confirm the camera is connected and not held by Zoom/Teams/OBS/QuickTime."
    if [[ "$(uname)" == "Darwin" ]]; then
      echo "  - macOS gates camera access: grant your terminal permission under"
      echo "    System Settings > Privacy & Security > Camera, then re-run."
    fi
    echo "  - Or pass the device explicitly:"
    echo "      bash scripts/start_webcam.sh $IP /dev/video0   # Linux"
    echo "      bash scripts/start_webcam.sh $IP 0             # macOS/Windows index"
    exit 1
  fi
  echo "    Detected webcam: $DEVICE"
fi

# ── 6. Pre-flight the device ──────────────────────────────────────────────────
# An open device is NOT proof of a usable feed: a camera whose privacy shutter is
# closed, or one still ramping its auto-exposure, hands back all-zero buffers
# while read() reports success -- the feed then streams pure black with no error
# anywhere in the stack. Catch that here, loudly, instead of after someone
# reports "the video is blank".
echo ""
echo "==> Pre-flighting webcam (open + non-black frame check)..."
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
    print("    NOTE: webcam did not honor the requested resolution; it will stream what it negotiated.")

# Discard warm-up frames: webcams need a moment for auto-exposure/white balance
# to converge, and the first frames are routinely black or badly exposed.
for _ in range(10):
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
    print("    FAIL: webcam opened but returned no frames.")
    sys.exit(1)
if peak == 0:
    print("")
    print("    FAIL: every sampled frame was pure black (peak pixel value 0).")
    print("    Usual causes: a closed privacy shutter or lens cap, a camera")
    print("    still held by another app that has muted the feed, or an OS")
    print("    privacy setting handing out a blanked stream. Streaming this")
    print("    would produce a blank feed.")
    sys.exit(2)

print("    OK: live frames contain real picture data.")
PY
PREFLIGHT=$?
set -e

if [[ $PREFLIGHT -ne 0 ]]; then
  echo ""
  echo "Aborting before publish: the webcam would stream an unusable feed."
  echo "The Docker stack is still running -- fix the device and re-run this script,"
  echo "or stop the stack with: ${COMPOSE[*]} --profile demo down"
  exit 1
fi

# ── 7. Start the live ingest publisher ────────────────────────────────────────
echo ""
echo "==> Starting streammark-ingest from webcam '$DEVICE' (Ctrl+C to stop)..."
echo "    Watch at: http://$IP:5173/room/$ROOM"
echo ""
exec streammark-ingest \
  --room "$ROOM" \
  --device "$DEVICE" \
  --width "$CAP_WIDTH" \
  --height "$CAP_HEIGHT" \
  --fps "$CAP_FPS"
