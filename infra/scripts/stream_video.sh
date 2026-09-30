#!/usr/bin/env bash
# Streams the WhatsApp demo video into the LiveKit demo-room.
# Run from the infra/ directory: bash scripts/stream_video.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$INFRA_DIR/.." && pwd)"
SHARED_DIR="$REPO_ROOT/shared"
PUBLISHER_DIR="$REPO_ROOT/stream-publisher"
VIDEO="$SCRIPT_DIR/../../../Vision/210526-1254.mp4"
VENV="$PUBLISHER_DIR/.venv"

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

# Install the packages if not already installed
if ! python -c "import streammark_publisher" 2>/dev/null; then
  echo "Installing streammark-shared + streammark-publisher packages..."
  pip install -e "$SHARED_DIR" -e "$PUBLISHER_DIR" --quiet
fi

echo "Starting dummy publisher for: $VIDEO"
python "$PUBLISHER_DIR/scripts/dummy_publisher.py" \
  --room demo-room \
  --video "$VIDEO"
