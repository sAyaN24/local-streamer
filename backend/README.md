# StreamMark Backend

LiveKit-powered backend for StreamMark: a capture-card video source is published into a
self-hosted LiveKit room, viewers join over WebRTC, and every viewer's annotations ride
LiveKit's data channel so everyone sees everyone else's markup live. Room metadata, user
accounts, and a full annotation history are persisted in MongoDB.

```
[Capture card] --OpenCV--> [ingest service] --rtc.VideoSource--> [livekit-server SFU] <--WebRTC--> [viewers]
                                                                        |
                                                        data channel (annotations, fan-out)
                                                                        v
[api service] <--auth/rooms/tokens--> [MongoDB]              [logger bot] (persists annotation events)
```

- **`api`** (FastAPI): user auth, room lifecycle (create/list/go-live/end), viewer token
  minting, health checks. Backed by MongoDB for users/rooms and by LiveKit's `RoomService`
  for live room state.
- **`ingest`**: reads a capture card via OpenCV/V4L2 and publishes it into a LiveKit room as
  the sole video source.
- **`tools/logger_bot`**: headless participant that persists every annotation data-channel
  message to MongoDB (`annotations` collection) for future replay/audit.
- **`tools/mint_publisher_token`**: manual debug CLI, never exposed over HTTP.

## Prerequisites

- Python 3.12+
- Docker + Docker Compose
- A Linux host with the capture card attached (`v4l2-ctl --list-formats-ext -d /dev/videoN`
  to discover its real supported resolutions/framerates/pixel formats before deploying)

## Quick start (dev)

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

docker compose up -d livekit mongo   # SFU + database
python -m streammark.api.__main__    # or: streammark-api

# In a separate terminal, once you have a real capture card attached:
streammark-ingest --room shared-stream --device /dev/video0
```

## Quick start (all containerized, except ingest)

```bash
cp .env.example .env
docker compose up -d --build   # livekit + mongo + api + frontend
streammark-ingest --room shared-stream --device /dev/video0   # still runs on the host
```

The ingest service is intentionally **not** a compose service by default — it needs direct
access to the capture card's `/dev/videoN` device node. `docker-compose.yml` has a commented-out
containerized fallback (with `--device` passthrough) if you must run it in Docker anyway.

## Environment variables

| Var | Default | Used by |
|---|---|---|
| `LIVEKIT_URL` | `ws://localhost:7880` | api, ingest, tools |
| `LIVEKIT_API_KEY` | `devkey` | api, ingest, tools |
| `LIVEKIT_API_SECRET` | dev placeholder (32+ chars) | api, ingest, tools |
| `CAPTURE_DEVICE` | `/dev/video0` | ingest |
| `CAPTURE_FOURCC` | `MJPG` | ingest |
| `VIDEO_WIDTH` / `VIDEO_HEIGHT` | `1920` / `1080` | ingest |
| `VIDEO_FPS` | `60` | ingest |
| `VIDEO_BITRATE_KBPS` | `8000` | ingest |
| `VIDEO_CODEC` | `h264` | ingest |
| `SIMULCAST_ENABLED` | `false` | ingest |
| `DEFAULT_ROOM_NAME` | `shared-stream` | ingest |
| `ROOM_EMPTY_TIMEOUT_SEC` / `ROOM_DEPARTURE_TIMEOUT_SEC` / `ROOM_MAX_PARTICIPANTS` | `300` / `20` / `60` | api |
| `VIEWER_TOKEN_TTL_MINUTES` / `PUBLISHER_TOKEN_TTL_MINUTES` | `360` / `720` | api, ingest, tools |
| `MONGODB_URI` | `mongodb://localhost:27017` | api, tools/logger_bot |
| `MONGODB_DB_NAME` | `streammark` | api, tools/logger_bot |
| `AUTH_JWT_SECRET` | dev placeholder | api |
| `AUTH_TOKEN_TTL_MINUTES` | `1440` | api |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | api |
| `CORS_ALLOW_ORIGINS` | `*` | api |
| `LOG_LEVEL` | `INFO` | all |
| `INGEST_RECONNECT_INITIAL_BACKOFF_SEC` / `_MAX_BACKOFF_SEC` | `0.5` / `10.0` | ingest |
| `INGEST_CAPTURE_REOPEN_INTERVAL_SEC` | `2.0` | ingest |
| `INGEST_CAPTURE_MAX_CONSECUTIVE_READ_FAILURES` | `30` | ingest |
| `METRICS_LOG_INTERVAL_SEC` | `5.0` | ingest |

`LIVEKIT_API_SECRET` and `AUTH_JWT_SECRET` are **two different, dev-only placeholder secrets**.
Rotate both before any deployment that isn't a fully trusted, air-gapped LAN.

## API reference

All bodies/responses are JSON.

```bash
# Sign up / log in (returns a bearer token for the app's own session -- separate from LiveKit's tokens)
curl -X POST localhost:8000/auth/signup -d '{"email":"a@b.com","password":"password123","name":"Amy"}'
curl -X POST localhost:8000/auth/login  -d '{"email":"a@b.com","password":"password123"}'
curl localhost:8000/auth/me -H "Authorization: Bearer <token>"

# Create a room (host-only; go_live=true also stands the room up in LiveKit immediately)
curl -X POST localhost:8000/rooms -H "Authorization: Bearer <token>" \
  -d '{"id":"ot-room-1","title":"Cardiac Review","go_live":true}'

# Start a previously-scheduled room
curl -X POST localhost:8000/rooms/ot-room-1/go-live -H "Authorization: Bearer <token>"

# List all rooms (public -- scheduled/live/ended, live ones include real participant counts)
curl localhost:8000/rooms

# Mint a viewer join token (public -- no account required to watch/annotate)
curl "localhost:8000/rooms/ot-room-1/token?identity=viewer1&name=Viewer%20One"

# End a room (host-only)
curl -X DELETE localhost:8000/rooms/ot-room-1 -H "Authorization: Bearer <token>"

# Health
curl localhost:8000/healthz
```

Interactive docs at `http://localhost:8000/docs` once the api service is running.

## Multi-room usage

Each ingest process handles one capture card publishing into one room. For multiple physical
rooms/capture cards against the same `livekit-server`, run one process per room:

```bash
streammark-ingest --room ot-room-1 --device /dev/video0
streammark-ingest --room ot-room-2 --device /dev/video2
```

## Latency tuning notes

- `CAP_PROP_BUFFERSIZE=1` minimizes the V4L2 driver's internal frame queue.
- **FOURCC matters**: most USB capture cards cannot sustain uncompressed YUYV at 1080p60
  (USB2 bandwidth ceiling ~480Mbps vs. ~3Gbps needed) but can do hardware-compressed MJPG at
  that resolution/rate. `CAPTURE_FOURCC=MJPG` is the default for this reason — confirm your
  card's actual supported formats with `v4l2-ctl --list-formats-ext -d /dev/videoN` before
  deploying, and watch the ingest logs for "not honored by device" warnings.
- V4L2 devices frequently clamp/ignore requested resolution/fps/format silently — every
  requested value is read back after opening the device and logged if it doesn't match.
- **No hardware encoder was available on the reference dev machine** (no NVIDIA/VAAPI). CPU-only
  software H.264 encode of 1080p60 may not fit under an 80ms glass-to-glass budget on similar
  hardware. All video profile knobs (`VIDEO_WIDTH/HEIGHT/FPS/BITRATE_KBPS`) are independent env
  vars specifically so lowering resolution/fps/bitrate is a config change, not a code change.
  2K@60 (`VIDEO_WIDTH=2560 VIDEO_HEIGHT=1440`) is fully supported the same way but is likely to
  exceed the latency budget without a hardware encoder.
- Simulcast is off by default (`SIMULCAST_ENABLED=false`) — on a LAN with ample bandwidth,
  simulcast only adds encode CPU cost for no benefit, directly working against the latency
  budget.
- At the 8Mbps default bitrate with simulcast off, 50 concurrent viewers means the
  `livekit-server` host needs to sustain roughly 8Mbps × 50 ≈ **400Mbps** of aggregate egress —
  comfortable on a wired LAN/switch, but confirm against your actual deployment NIC before
  relying on it (1GbE has headroom; anything less might not).
- capture → publish is deliberately split across a dedicated OS thread (blocking
  `cv2.VideoCapture.read()`) and the asyncio publish loop, connected by a depth-1 drop-oldest
  queue — never merge these back into one coroutine, or a slow capture read will stall the
  LiveKit SDK's own internal reconnect/keepalive tasks.

## Logger bot (annotation history)

```bash
streammark-logger-bot --room ot-room-1 --out annotations.log
```

Joins as a hidden, data-channel-only participant and persists every annotation event to
MongoDB's `annotations` collection (`{room, sender, topic, payload, ts}`), plus optionally a
local JSON-lines file for quick debugging.

## Known limitations

- **This isn't validated against a real capture card.** Development/testing happened on a
  sandbox without real capture-card hardware — the ingest path (`capture.py`, `publisher.py`)
  is correct-by-inspection against the documented OpenCV/V4L2 API, but real-world FOURCC
  support, negotiated resolution/fps, and actual glass-to-glass latency all need on-site
  validation with the real hardware before trusting the numbers in this document.
- Dev-only credentials (`devkey` / `devsecret-...` / `devauthsecret-...`) ship in `.env.example`
  and `docker/livekit.yaml` — rotate all three before any non-fully-trusted-LAN deployment.
- TURN is off by default in `docker/livekit.yaml` (LiveKit's built-in TURN needs a real domain
  for TLS or a UDP-only setup) — see the comments in that file to enable it.
- No rate limiting / account lockout on `/auth/login` — fine for a trusted LAN, not for
  internet-facing deployment.

## WAN-scaling / future extensibility

Both video and annotations flow through LiveKit's SFU abstraction rather than bespoke sockets,
so moving to WAN is a deployment/config change, not a rearchitecture: flip
`rtc.use_external_ip: true` in `docker/livekit.yaml`, deploy a real TURN server with a domain,
re-enable simulcast, and optionally move to a multi-node LiveKit mesh with Redis — no changes
needed to the ingest or API service code.
