# infra

Docker Compose stack (LiveKit, MongoDB, [`backend-webserver`](../backend-webserver)
API, [`frontend`](../frontend), and an nginx `proxy` in front of both) and the
orchestration scripts that bring it up alongside
[`stream-publisher`](../stream-publisher), which always runs natively on the
capture host. See the root [README](../README.md) for the full guide; this
folder just holds the pieces:

- `docker-compose.yml` — the stack. `api` and `frontend` pull the images
  published by `.github/workflows/docker-build.yml`; `livekit`/`mongo`/`seed`
  use upstream images. Neither `api` nor `frontend` publishes a host port --
  `proxy` is the single entry point, routing `/` to the frontend and `/api/`
  to the API (stripped before forwarding; see `docker/proxy.conf`).
- `docker/` — `livekit.yaml`, `proxy.conf` (mounted into the `proxy`
  service), and `api.Dockerfile` (the source the CI workflow builds from; not
  used by this compose file directly, which pulls the published image
  instead).
- `scripts/` — `start_capture.sh` (the live capture-card launcher),
  `seed_admin.py` (runs as the one-shot `seed-admin` compose service; creates
  the first admin login and prints it to that service's logs), and
  `seed_demo_room.py` (runs as the one-shot `seed` compose service).
- `.env.example` — copy to `.env` and fill in real secrets before running
  anything here. `start_capture.sh` rewrites `LIVEKIT_URL` in `.env` and
  `node_ip` in `docker/livekit.yaml` to match your LAN IP on every run --
  that's the only URL that needs it, since browsers connect to LiveKit's
  WS/RTC signaling directly. The API URL doesn't: the frontend defaults to
  same-origin `/api/`, which the proxy makes correct regardless of LAN IP.

Run `bash scripts/start_capture.sh` from this directory, or
`bash infra/scripts/start_capture.sh` from the repo root. Once up, everything
is reachable at `http://<LAN-IP>/` (frontend) and
`http://<LAN-IP>/api/...` (API) -- see `docker/proxy.conf`.
