#!/usr/bin/env bash
# Builds dist/streammark-publisher -- a single-file Linux x86_64 executable:
# run it (with a .env alongside it, see .env.example) and it auto-detects the
# capture card (V4L2 /dev/video*) and starts publishing. No Python install
# required on the target machine.
#
# Usage: bash stream-publisher/packaging/build_linux.sh [--clean]
#
# Needs: Python >= 3.12 on PATH, and (for opencv-python, which links against
# libGL even though this project never opens a GUI window) libgl1 +
# libglib2.0-0 installed -- `sudo apt-get install -y libgl1 libglib2.0-0`.
# The target machine running the built executable needs the same two
# libraries installed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLISHER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PUBLISHER_DIR/.." && pwd)"
VENV="$PUBLISHER_DIR/.venv"

CLEAN=0
[[ "${1:-}" == "--clean" ]] && CLEAN=1

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

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "==> Creating venv at $VENV"
  BASE_PY="$(find_python)" || {
    echo "Error: no Python >=3.12 found on PATH." >&2
    exit 1
  }
  "$BASE_PY" -m venv "$VENV"
fi
VPY="$VENV/bin/python"

echo "==> Installing streammark-shared + streammark-publisher[build]"
"$VPY" -m pip install --upgrade pip --quiet
(cd "$REPO_ROOT" && "$VPY" -m pip install -e ./shared -e "./stream-publisher[build]" --quiet)

if [[ "$CLEAN" -eq 1 ]]; then
  echo "==> Cleaning previous build artifacts"
  rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist"
fi

echo "==> Building streammark-publisher with PyInstaller"
(cd "$SCRIPT_DIR" && "$VPY" -m PyInstaller --noconfirm streammark_publisher.spec)

DIST_BIN="$SCRIPT_DIR/dist/streammark-publisher"
if [[ -x "$DIST_BIN" ]]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/dist/.env.example"
  echo ""
  echo "==> Done: $DIST_BIN"
  echo "    Copy dist/.env.example to dist/.env next to it and fill in"
  echo "    LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET / DEFAULT_ROOM_NAME,"
  echo "    then run it: ./streammark-publisher"
else
  echo "Build failed -- see PyInstaller output above." >&2
  exit 1
fi
