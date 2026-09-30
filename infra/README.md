# infra

Docker Compose stack (LiveKit, MongoDB, [`backend-webserver`](../backend-webserver)
API, [`frontend`](../frontend)) and the orchestration scripts that bring it up
alongside [`stream-publisher`](../stream-publisher), which always runs natively
on the capture host. See the root [README](../README.md) for the full guide;
this folder just holds the pieces:

- `docker-compose.yml` — the stack. `api` and `dummy-publisher` build with the
  repo root as context (they need `shared/` and their own component folder as
  siblings); `frontend` builds from `../frontend` directly.
- `docker/` — `livekit.yaml` and the two Dockerfiles built by compose.
- `scripts/` — `start*.sh` launchers (dummy video / capture card / webcam),
  `stream_video.sh`, and `seed_demo_room.py` (runs as the one-shot `seed`
  compose service).
- `.env.example` — copy to `.env` and fill in real secrets before running
  anything here. The `start*.sh` scripts rewrite `LIVEKIT_URL` in `.env`,
  `node_ip` in `docker/livekit.yaml`, and `VITE_API_BASE_URL` in
  `docker-compose.yml` to match your LAN IP on every run.

Run `bash scripts/start.sh` (or `start_capture.sh` / `start_webcam.sh`) from
this directory, or `bash infra/scripts/start.sh` from the repo root.
