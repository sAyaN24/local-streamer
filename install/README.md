# Ubuntu/Debian installer

Bootstraps a fresh Ubuntu or Debian box to run the full Local Streamer
(StreamMark) stack — LiveKit, MongoDB, the API, and the frontend, via the
existing `infra/docker-compose.yml` — as a systemd-managed service that
comes back up automatically after a reboot.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/sAyaN24/local-streamer/main/install/setup.sh -o setup.sh
sudo bash setup.sh
```

Or, from a local checkout:

```bash
sudo bash install/setup.sh
```

What it does:
1. Installs base packages (`git`, `curl`, `python3`, `build-essential`, ...).
2. Installs Python 3.12 if the system default is older (via the deadsnakes
   PPA on Ubuntu; on Debian without it, this step is skipped with a warning
   and only affects the native capture-card publisher, not the Docker
   services).
3. Installs Docker Engine + the Compose plugin from Docker's official apt
   repo, enables the `docker` service, and adds the invoking user to the
   `docker` group.
4. Clones (or, on re-run, `git pull`s) the repo into `/opt/local-streamer`.
   With `--skip-publisher`, this is a sparse checkout of just `infra/` and
   `install/` instead of the whole repo, since `api`/`frontend` run from the
   published GHCR images (see `infra/docker-compose.yml`) and don't need
   `backend-webserver/`/`frontend/`/`stream-publisher/`/`shared/` source on
   disk at all.
5. Creates `infra/.env` from `infra/.env.example` if it doesn't exist yet,
   and fills in this box's LAN IP for `LIVEKIT_URL`.
6. Sets up a native Python venv for `stream-publisher` (the capture-card
   ingest tool, which needs direct `/dev/videoN` access and so runs outside
   Docker) — skip with `--skip-publisher` if this box has no capture card.
7. Installs and enables a `streammark.service` systemd unit that runs
   `docker compose up -d` on boot. Containers use `restart: unless-stopped`,
   so they also survive Docker daemon restarts on their own.

Useful flags: `--repo <url>`, `--branch <name>`, `--dir <path>`,
`--skip-publisher`, `--no-start` (install everything but don't start yet —
use this if you want to edit `infra/.env` first). See `setup.sh --help`.

**Before exposing the box beyond localhost**, edit
`/opt/local-streamer/infra/.env` and replace the placeholder
`LIVEKIT_API_SECRET` / `AUTH_JWT_SECRET` values, then
`sudo systemctl restart streammark`.

## Manage the service

```bash
sudo systemctl status streammark
sudo systemctl restart streammark
sudo systemctl stop streammark
docker compose -f /opt/local-streamer/infra/docker-compose.yml logs -f
```

## Uninstall

```bash
sudo bash install/uninstall.sh          # stops + disables the service only
sudo bash install/uninstall.sh --all     # + deletes data, the repo, and installed packages
```

By default `uninstall.sh` only stops and disables the systemd service —
nothing destructive happens unless you ask for it:

| Flag                | Effect |
|----------------------|--------|
| `--purge-data`       | `docker compose down -v` — deletes the MongoDB volume (all app data) |
| `--purge-repo`       | Deletes `/opt/local-streamer` (repo + `infra/.env` secrets) |
| `--purge-packages`   | Purges Docker Engine and, only if `setup.sh` itself installed it via the deadsnakes PPA, Python 3.12. Never touches a pre-existing Docker/Python install. |
| `--all`              | All of the above |
| `-y`, `--yes`        | Skip the confirmation prompt |

Base packages (`git`, `curl`, `build-essential`, etc.) are never removed —
they're too likely to be depended on by other things on the box.
