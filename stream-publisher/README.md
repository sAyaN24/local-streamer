# streammark-publisher

Capture-card video ingestion: publishes a live feed (plus pupil-tracking
overlay data on the `pupil` data-channel topic) into a LiveKit room. Ships the
`streammark-ingest` CLI, and `scripts/detect_capture_device.py`, which
auto-detects which camera index/device path is the external capture card.

This package **must run natively**, not in a container: Docker cannot pass a
USB capture device through to a container on macOS/Windows. See the root
[README](../README.md) and [`infra/scripts/`](../infra/scripts) for the
launchers that set this up automatically. To run by hand:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../shared -e .
streammark-ingest --room demo-room --device /dev/video0
```

Requires `infra/.env` (copy from `infra/.env.example`) to be readable from the
current working directory, or the equivalent environment variables set
directly — see `streammark_shared.config.Settings`.
