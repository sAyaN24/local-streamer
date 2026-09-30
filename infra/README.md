# infra

Docker Compose stack (LiveKit, MongoDB, [`backend-webserver`](../backend-webserver)
API, [`frontend`](../frontend)) and the orchestration scripts that bring it up
alongside [`stream-publisher`](../stream-publisher), which always runs natively
on the capture host. See the root [README](../README.md) for the full guide;
this folder just holds the pieces:

- `docker-compose.yml` — the stack. `api` and `frontend` pull the images
  published by `.github/workflows/docker-build.yml`; `livekit`/`mongo`/`seed`
  use upstream images.
- `docker/` — `livekit.yaml` and `api.Dockerfile` (the source the CI workflow
  builds from; not used by this compose file directly, which pulls the
  published image instead).
- `scripts/` — `start_capture.sh` (the live capture-card launcher) and
  `seed_demo_room.py` (runs as the one-shot `seed` compose service).
- `.env.example` — copy to `.env` and fill in real secrets before running
  anything here. `start_capture.sh` rewrites `LIVEKIT_URL` in `.env` and
  `node_ip` in `docker/livekit.yaml` to match your LAN IP on every run, and
  passes `VITE_API_BASE_URL` to `docker compose up` so the frontend
  container's entrypoint picks up the right API URL at start.

Run `bash scripts/start_capture.sh` from this directory, or
`bash infra/scripts/start_capture.sh` from the repo root.
