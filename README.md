# StreamMark — local streamer

LiveKit-powered capture-card streaming with a real-time annotation and
pupil-tracking overlay. The stack (LiveKit, MongoDB, API, frontend, and an
nginx proxy in front of both frontend and API) runs in Docker; the video
publisher (the capture card) always runs natively.

## Repository layout

- [`infra/`](infra) — Docker Compose stack, Dockerfiles, LiveKit config, and
  the orchestration scripts (`start*.sh`) that bring everything up. `proxy`
  is the single HTTP entry point: `/` routes to the frontend, `/api/` to the
  backend.
- [`backend-webserver/`](backend-webserver) — FastAPI room/auth/token service
  (`streammark-api`), plus its DB-backed tools (`streammark-logger-bot`,
  `streammark-mint-token`).
- [`stream-publisher/`](stream-publisher) — capture-card video ingestion
  (`streammark-ingest`) and its capture-device auto-detect helper. Always
  runs natively, never in a container.
- [`shared/`](shared) — config, logging, and LiveKit token-minting code used
  by both `backend-webserver` and `stream-publisher`.
- [`frontend/`](frontend) — the React/Vite viewer, dashboard, and annotation UI.

## Prerequisites

- **Docker** with Compose. Verify with `docker compose version`. If that prints
  `unknown command`, your Docker CLI has no Compose plugin — link the standalone
  binary once:
  ```bash
  mkdir -p ~/.docker/cli-plugins
  ln -sf "$(command -v docker-compose)" ~/.docker/cli-plugins/docker-compose
  ```
- **Python >= 3.12** — needed to run the capture-card publisher, which must
  run natively (Docker cannot pass a USB capture device through on
  macOS/Windows). macOS ships 3.9, so install a newer one:
  `brew install python@3.12`.
- `infra/.env` — copy from `infra/.env.example` and fill in real secrets; see
  that file for the full variable list.

## Running

`start_capture.sh` auto-detects the machine's LAN IP and rewrites it into
`infra/.env`, `infra/docker/livekit.yaml`, and `infra/docker-compose.yml`, so
other devices on the same network can connect. Pass an IP explicitly to
override. It starts with `docker compose down`, so it replaces any running stack.

```bash
bash infra/scripts/start_capture.sh                             # auto-detect
bash infra/scripts/start_capture.sh 192.168.0.108               # explicit IP
bash infra/scripts/start_capture.sh 192.168.0.108 /dev/video0   # explicit device
```

The second argument overrides device detection — a `/dev/videoN` path on Linux,
or an integer index on macOS/Windows. Tune the feed with `ROOM`, `CAP_WIDTH`,
`CAP_HEIGHT`, `CAP_FPS` environment variables (defaults: `demo-room`,
1920x1080, 30fps).

Before publishing, the script pre-flights the device: it opens it, samples
frames, and **aborts if every frame is black** rather than streaming a blank
feed. It also creates the venv (under `stream-publisher/.venv`) with a
Python >= 3.12 interpreter, recreating an older one if present.

### Stopping

```bash
cd infra && docker compose down
```

## Access

With the stack up (substitute your LAN IP). Frontend and API share one origin
via the `proxy` service (backend under `/api/`) — no LAN IP needs to be known
by the frontend itself, only by your browser to reach it:

| What | URL |
|---|---|
| Viewer (no login) | `http://<IP>:8080/room/demo-room` |
| Login / dashboard | `http://<IP>:8080/login` |
| API | `http://<IP>:8080/api/...` |
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
`progressive` (e.g. `tt`, `bb`) will fail. Fix by setting the capture card's
source to a progressive mode (1080p, not 1080i). `start_capture.sh` detects
this before publishing.

**`unknown flag: --remove-orphans`** — the Docker CLI has no Compose plugin.
See Prerequisites.

**`pip install -e` fails / "editable mode requires setuptools"** — the venv is
on a Python older than 3.12. Delete `stream-publisher/.venv` and re-create it
with a newer interpreter; `start_capture.sh` does this automatically.

**Viewer shows nothing after restarting the publisher** — the browser is still
subscribed to a track that no longer exists. Hard-reload the page.

## Helper processes

**Logger bot** (`streammark-logger-bot`, entry point
`backend-webserver/src/streammark_webserver/tools/logger_bot.py`) — joins as a
hidden, data-only participant and persists every annotation event to
MongoDB's `annotations` collection:

```bash
streammark-logger-bot --room demo-room --out annotations.log
```

`--out` is optional (mirrors events to a local JSON-lines file for debugging).

It needs `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` (from
`infra/.env`) and a Python >= 3.12 env with `backend-webserver`'s packages
installed:

```bash
cd backend-webserver
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../shared -e ".[dev]"
```
