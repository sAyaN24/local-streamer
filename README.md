# StreamMark — local streamer

LiveKit-powered capture-card streaming with a real-time annotation and
pupil-tracking overlay. The stack (LiveKit, MongoDB, API, frontend) runs in
Docker; the video publisher runs either as a container (dummy video) or
natively (live capture card).

## Prerequisites

- **Docker** with Compose. Verify with `docker compose version`. If that prints
  `unknown command`, your Docker CLI has no Compose plugin — link the standalone
  binary once:
  ```bash
  mkdir -p ~/.docker/cli-plugins
  ln -sf "$(command -v docker-compose)" ~/.docker/cli-plugins/docker-compose
  ```
- **Python >= 3.12** — only needed for live capture-card mode, which must run
  natively (Docker cannot pass a USB capture device through on macOS/Windows).
  Not needed for dummy-video mode. macOS ships 3.9, so install a newer one:
  `brew install python@3.12`.
- `backend/.env` — see `backend/README.md` for the full variable list.

## Running

Both launchers auto-detect the machine's LAN IP and rewrite it into `.env`,
`docker/livekit.yaml`, and `docker-compose.yml`, so other devices on the same
network can connect. Pass an IP explicitly to override.

Each script starts with `docker compose down`, so it replaces any running stack.

### Option A — dummy video (no hardware)

Runs the full stack plus a containerized publisher that loops a local video
file into `demo-room`. Everything runs in Docker; no local Python required.

```bash
bash backend/scripts/start.sh                 # auto-detect LAN IP
bash backend/scripts/start.sh 192.168.0.108   # explicit IP
```

Choose the video with `DUMMY_PUBLISHER_VIDEO_FILE` / `DUMMY_PUBLISHER_VIDEO_DIR`
in `backend/.env` (directory defaults to `../../Vision`). The file must be
**progressive** — see Troubleshooting.

To (re)start only the publisher against an already-running stack:

```bash
cd backend
docker compose --profile demo up -d --build dummy-publisher
```

### Option B — live capture card

Runs the full stack **without** any dummy video, then publishes the real
capture card into `demo-room` via `streammark-ingest`.

```bash
bash backend/scripts/start_capture.sh                             # auto-detect
bash backend/scripts/start_capture.sh 192.168.0.108               # explicit IP
bash backend/scripts/start_capture.sh 192.168.0.108 /dev/video0   # explicit device
```

The second argument overrides device detection — a `/dev/videoN` path on Linux,
or an integer index on macOS/Windows. Tune the feed with `ROOM`, `CAP_WIDTH`,
`CAP_HEIGHT`, `CAP_FPS` environment variables (defaults: `demo-room`,
1920x1080, 30fps).

Before publishing, the script pre-flights the device: it opens it, samples
frames, and **aborts if every frame is black** rather than streaming a blank
feed. It also creates the venv with a Python >= 3.12 interpreter, recreating an
older one if present.

### Option C — webcam

Same as Option B, but publishes a built-in or plain USB webcam instead of a
capture card.

```bash
bash backend/scripts/start_webcam.sh                             # auto-detect
bash backend/scripts/start_webcam.sh 192.168.0.108               # explicit IP
bash backend/scripts/start_webcam.sh 192.168.0.108 0             # explicit device
```

The only real difference from `start_capture.sh` is device selection: a capture
card enumerates *after* the built-in camera, so `start_capture.sh` prefers the
highest working index while `start_webcam.sh` prefers a webcam-looking name and
falls back to the **lowest** working index. Defaults are also webcam-friendly —
1280x720 @ 30fps, since most webcams negotiate 720p far more reliably than
1080p. Override with the same `ROOM`, `CAP_WIDTH`, `CAP_HEIGHT`, `CAP_FPS`
environment variables.

The same pre-flight runs before publishing. If it aborts with an all-black
frame, the usual causes are a closed privacy shutter, another app (Zoom, Teams,
OBS) holding the camera, or a denied OS camera permission — on macOS, grant your
terminal access under System Settings > Privacy & Security > Camera.

### Stopping

```bash
cd backend && docker compose --profile demo down
```

## Access

With the stack up (substitute your LAN IP):

| What | URL |
|---|---|
| Viewer (no login) | `http://<IP>:5173/room/demo-room` |
| Login / dashboard | `http://<IP>:5173/login` |
| API | `http://<IP>:8000` |
| LiveKit signaling | `ws://<IP>:7880` |

The seed service creates a demo host account on every start:
`demo@streammark.example` / `demo12345`.

MongoDB is intentionally not published to the host; it is reachable only as
`mongo:27017` inside the Compose network.

## Troubleshooting

**Video plays but the picture is black.** The source is almost certainly
interlaced. OpenCV cannot deinterlace: `sws_scale` fails per frame and returns a
zeroed buffer while `cap.read()` still reports success, so the stack streams
pure black with no error anywhere. Check with
`ffprobe -show_entries stream=field_order <file>` — anything other than
`progressive` (e.g. `tt`, `bb`) will fail. Fixes:

- Capture card: set the source to a progressive mode (1080p, not 1080i).
- Video file: transcode once with a deinterlace filter.
  ```bash
  ffmpeg -i input.mp4 -vf "yadif=0,scale=1280:720" -r 30 -an \
         -c:v libx264 -crf 23 output.mp4
  ```
  1280x720 matches the publisher's internal frame size, so downscaling here
  costs nothing.

`start_capture.sh` detects this before publishing; `start.sh` does not.

**`unknown flag: --remove-orphans`** — the Docker CLI has no Compose plugin.
See Prerequisites.

**`pip install -e` fails / "editable mode requires setuptools"** — the venv is
on a Python older than 3.12. Delete `backend/.venv` and re-create it with a
newer interpreter; `start_capture.sh` does this automatically.

**Viewer shows nothing after restarting the publisher** — the browser is still
subscribed to a track that no longer exists. Hard-reload the page.

## Helper processes

**Dummy publisher** (`backend/scripts/dummy_publisher.py`) — feeds a local video
file into a LiveKit room as a visible publisher, so you can test the
viewer/annotation flow without capture-card hardware:

```bash
python scripts/dummy_publisher.py --room demo-room --video /path/to/sample.mp4
```

The target room must already exist in the API before you point the publisher at
it. `demo-room` is created and set live by the seed service.

**Logger bot** (`streammark-logger-bot`, entry point
`src/streammark/tools/logger_bot.py`) — joins as a hidden, data-only participant
and persists every annotation event to MongoDB's `annotations` collection:

```bash
streammark-logger-bot --room demo-room --out annotations.log
```

`--out` is optional (mirrors events to a local JSON-lines file for debugging).

Both need `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` (from `.env`)
and a Python >= 3.12 env with the project installed:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```
