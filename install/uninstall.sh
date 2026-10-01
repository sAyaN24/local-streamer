#!/usr/bin/env bash
# Reverses install/setup.sh. By default this only stops/disables the
# systemd service(s) -- streammark and, if present, streammark-publisher
# (the safe, non-destructive part). Everything that
# destroys data or removes system packages is opt-in via flags, because
# this box's Docker/Python may be used by things other than this project.
#
# Usage (as root or via sudo):
#   sudo bash install/uninstall.sh [options]
#
# Options:
#   --dir <path>        Install directory (default: /opt/local-streamer,
#                        must match what setup.sh used)
#   --purge-data         Also `docker compose down -v`: deletes the MongoDB
#                        volume (mongo-data) and all app data. Irreversible.
#   --purge-repo          Also delete the install directory (the cloned repo,
#                        infra/.env, and any secrets in it). Irreversible.
#   --purge-packages       Also apt-get purge Docker Engine and, if this
#                        script's setup.sh installed it, the deadsnakes
#                        python3.12 packages -- but only the ones setup.sh
#                        itself added (detected via the apt source files it
#                        created), never a Docker/Python that predates it or
#                        that something else on the box depends on.
#   --all                Shorthand for --purge-data --purge-repo --purge-packages
#   -y, --yes             Don't prompt for confirmation
#
# Always leaves alone: git, curl, ca-certificates, build-essential and other
# generic base packages -- removing those is too likely to break unrelated
# things on a shared box, so that's left to you if you really want it gone.

set -euo pipefail

INSTALL_DIR="/opt/local-streamer"
SERVICE_NAME="streammark"
PUBLISHER_SERVICE_NAME="streammark-publisher"
PURGE_DATA=0
PURGE_REPO=0
PURGE_PACKAGES=0
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --purge-data) PURGE_DATA=1; shift ;;
    --purge-repo) PURGE_REPO=1; shift ;;
    --purge-packages) PURGE_PACKAGES=1; shift ;;
    --all) PURGE_DATA=1; PURGE_REPO=1; PURGE_PACKAGES=1; shift ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

log() { echo -e "\n==> $*"; }
warn() { echo -e "\n!! $*" >&2; }
die() { echo -e "\nError: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "must be run as root (try: sudo bash $0)"

echo "This will:"
echo "  - stop and disable the '$SERVICE_NAME' and '$PUBLISHER_SERVICE_NAME' systemd services"
[[ "$PURGE_DATA" -eq 1 ]]     && echo "  - DELETE all Docker volumes for the stack (MongoDB data) [--purge-data]"
[[ "$PURGE_REPO" -eq 1 ]]     && echo "  - DELETE $INSTALL_DIR (repo + infra/.env secrets) [--purge-repo]"
[[ "$PURGE_PACKAGES" -eq 1 ]] && echo "  - apt-get purge Docker Engine and setup.sh-installed Python 3.12 [--purge-packages]"
if [[ "$PURGE_DATA" -eq 0 && "$PURGE_REPO" -eq 0 && "$PURGE_PACKAGES" -eq 0 ]]; then
  echo "  (nothing else -- pass --purge-data / --purge-repo / --purge-packages / --all for more)"
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p $'\nProceed? [y/N] ' reply
  [[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
fi

COMPOSE_FILE="$INSTALL_DIR/infra/docker-compose.yml"
ENV_FILE="$INSTALL_DIR/infra/.env"

# ── 1. Stop the stack ──────────────────────────────────────────────────────
if command -v docker &>/dev/null && [[ -f "$COMPOSE_FILE" ]]; then
  log "Stopping the Docker Compose stack..."
  if [[ "$PURGE_DATA" -eq 1 ]]; then
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans || true
  else
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans || true
  fi
else
  warn "compose file not found at $COMPOSE_FILE -- skipping 'docker compose down'."
fi

# ── 2. systemd service(s) ───────────────────────────────────────────────────
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
if [[ -f "$UNIT_PATH" ]]; then
  log "Stopping and disabling $SERVICE_NAME..."
  systemctl stop "$SERVICE_NAME" || true
  systemctl disable "$SERVICE_NAME" || true
  rm -f "$UNIT_PATH"
  systemctl daemon-reload
  systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true
else
  warn "$UNIT_PATH not found -- service already removed?"
fi

PUB_UNIT_PATH="/etc/systemd/system/${PUBLISHER_SERVICE_NAME}.service"
if [[ -f "$PUB_UNIT_PATH" ]]; then
  log "Stopping and disabling $PUBLISHER_SERVICE_NAME..."
  systemctl stop "$PUBLISHER_SERVICE_NAME" || true
  systemctl disable "$PUBLISHER_SERVICE_NAME" || true
  rm -f "$PUB_UNIT_PATH"
  systemctl daemon-reload
  systemctl reset-failed "$PUBLISHER_SERVICE_NAME" 2>/dev/null || true
fi

# ── 3. Built images ────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
  log "Removing images built for this project (streammark-*)..."
  docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' \
    | awk '/^streammark-/{print $2}' \
    | xargs -r docker rmi -f || true
fi

# ── 4. Repo directory ───────────────────────────────────────────────────────
if [[ "$PURGE_REPO" -eq 1 ]]; then
  if [[ -d "$INSTALL_DIR" ]]; then
    log "Deleting $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
  else
    warn "$INSTALL_DIR not found -- nothing to delete."
  fi
else
  log "Leaving $INSTALL_DIR in place (pass --purge-repo to delete it)."
fi

# ── 5. System packages ─────────────────────────────────────────────────────
if [[ "$PURGE_PACKAGES" -eq 1 ]]; then
  export DEBIAN_FRONTEND=noninteractive

  if [[ -f /etc/apt/sources.list.d/docker.list ]]; then
    log "Purging Docker Engine (installed by setup.sh's Docker apt repo)..."
    systemctl stop docker.socket docker.service 2>/dev/null || true
    apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || true
    rm -rf /var/lib/docker /var/lib/containerd
    rm -f /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.asc
  else
    warn "no infra/apt/sources.list.d/docker.list -- Docker wasn't installed by" \
         "setup.sh (or repo file already gone); leaving it alone."
  fi

  DEADSNAKES_LIST=(/etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-*.list)
  if [[ -e "${DEADSNAKES_LIST[0]}" ]]; then
    log "Purging Python 3.12 (installed by setup.sh via deadsnakes PPA)..."
    apt-get purge -y python3.12 python3.12-venv python3.12-dev || true
    add-apt-repository -y --remove ppa:deadsnakes/ppa || true
  else
    warn "deadsnakes PPA not present -- Python 3.12 on this box (if any) is the" \
         "distro's own package; leaving it alone."
  fi

  apt-get autoremove -y || true
  apt-get autoclean -y || true
else
  log "Leaving installed packages (Docker, Python 3.12) in place (pass --purge-packages to remove)."
fi

log "Uninstall complete."
