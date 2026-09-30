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

## Standalone executable

For a capture machine that only runs the publisher (no Python, no rest of the
repo), `streammark-publish` is a one-command version that always
auto-detects the capture card itself, sanity-checks it (open + non-black
frame check), and starts publishing — no `--device` flag needed:

```bash
streammark-publish --room demo-room
```

This is what gets packaged into a single-file executable by
[`packaging/`](packaging) (built for Linux x86_64 by
[`.github/workflows/build-publisher.yml`](../.github/workflows/build-publisher.yml)
on every push/tag — download the `streammark-publisher-linux-x86_64` artifact,
or grab the binary from a release). To build it yourself:

```bash
bash stream-publisher/packaging/build_linux.sh      # Linux
powershell -File stream-publisher\packaging\build_windows.ps1   # Windows
```

Both produce `stream-publisher/packaging/dist/streammark-publisher[.exe]`.
Copy `packaging/.env.example` to `.env` next to it, fill in
`LIVEKIT_URL`/`LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET`/`DEFAULT_ROOM_NAME` to
match the box running the Docker stack, and run it — it auto-detects the
capture card on every start.
