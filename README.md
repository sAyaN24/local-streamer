Dummy publisher (scripts/dummy_publisher.py) — feeds a local video file into a LiveKit room as a visible publisher, so you can test the viewer/annotation flow without capture-card hardware:
python scripts/dummy_publisher.py --room demo-room --video /path/to/sample.mp4
Note: demo-room already exists and is live (created by the seed service). The target room must already exist in the API before you point the publisher at it.

Logger bot (streammark-logger-bot, entry point for src/streammark/tools/logger_bot.py) — joins as a hidden, data-only participant and persists every annotation event to MongoDB's annotations collection:
streammark-logger-bot --room demo-room --out annotations.log
--out is optional (just mirrors events to a local JSON-lines file for debugging).

Both need LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET (from .env) and a Python env with the project installed:
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

Want me to set up the venv and actually run one of these against the current stack to confirm it works end-to-end?