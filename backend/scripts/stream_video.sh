#!/usr/bin/env bash
# Streams the WhatsApp demo video into the LiveKit demo-room.
# Run from the backend/ directory: bash scripts/stream_video.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VIDEO="$SCRIPT_DIR/WhatsApp Video 2026-07-07 at 14.19.27.mp4"
VENV="$BACKEND_DIR/.venv"

if [[ ! -f "$VIDEO" ]]; then
  echo "Error: video not found at: $VIDEO"
  exit 1
fi

# Create venv if it doesn't exist
if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

# Install the package if not already installed
if ! python -c "import streammark" 2>/dev/null; then
  echo "Installing streammark package..."
  pip install -e "$BACKEND_DIR/.[dev]" --quiet
fi

echo "Starting dummy publisher for: $VIDEO"
python "$SCRIPT_DIR/dummy_publisher.py" \
  --room demo-room \
  --video "$VIDEO"
