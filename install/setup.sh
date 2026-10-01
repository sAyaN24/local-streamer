#!/usr/bin/env bash
# Bootstraps a fresh Ubuntu/Debian box to run Local Streamer (StreamMark):
# installs Docker + the Python toolchain, clones/updates the repo, and
# installs a systemd service so the Docker Compose stack (LiveKit + MongoDB +
# API + frontend) comes up automatically on boot and stays up via Docker's
# own `restart: unless-stopped` policy. Also installs a second systemd service
# for the capture-card publisher (streammark-publish), which runs natively
# (not in Docker -- see the step 7 comment below) and retries on its own
# until a capture card is actually plugged in and usable.
#
# Usage (as root or via sudo):
#   sudo bash install/setup.sh [options]
#
# Options:
#   --repo <url>       Git URL to clone (default: public HTTPS URL below;
#                       for a private repo pass an SSH URL or an HTTPS URL
#                       with an embedded PAT)
#   --branch <name>     Branch to clone/track (default: main)
#   --dir <path>        Install directory (default: /opt/local-streamer)
#   --skip-publisher     Skip setting up the native Python venv for the
#                        capture-card publisher (stream-publisher); only
#                        needed if this box has the capture hardware attached.
#                        Also switches to a sparse checkout of just infra/ and
#                        install/ instead of the whole repo, since the Docker
#                        Compose stack runs off the published GHCR images and
#                        doesn't need backend-webserver/frontend/stream-
#                        publisher source at all.
#   --no-start           Install everything but don't start the service yet
#                        (use this if you still need to edit infra/.env)
#
# Safe to re-run: pulls the latest commit on $BRANCH instead of re-cloning,
# and re-installs the systemd unit idempotently.

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
# Disabled when not an interactive terminal or NO_COLOR is set (see
# https://no-color.org), so piping/redirecting this script's output (e.g.
# `setup.sh | tee install.log`) never ends up full of raw escape codes.
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]] && command -v tput &>/dev/null \
   && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  BOLD="$(tput bold)"; RESET="$(tput sgr0)"
  RED="$(tput setaf 1)"; GREEN="$(tput setaf 2)"
  YELLOW="$(tput setaf 3)"; CYAN="$(tput setaf 6)"
else
  BOLD=""; RESET=""; RED=""; GREEN=""; YELLOW=""; CYAN=""
fi

log()  { echo -e "\n${GREEN}${BOLD}==>${RESET} $*"; }
warn() { echo -e "\n${YELLOW}${BOLD}!!${RESET} ${YELLOW}$*${RESET}" >&2; }
die()  { echo -e "\n${RED}${BOLD}Error:${RESET} ${RED}$*${RESET}" >&2; exit 1; }
step() { echo -e "\n${CYAN}${BOLD}== $* ==========================================${RESET}"; }

banner() {
  echo -e "${CYAN}${BOLD}"
  cat <<'EOF'
 ____  _                            __  __            _
/ ___|| |_ _ __ ___  __ _ _ __ ___ |  \/  | __ _ _ __| | __
\___ \| __| '__/ _ \/ _` | '_ ` _ \| |\/| |/ _` | '__| |/ /
 ___) | |_| | |  __/ (_| | | | | | | |  | | (_| | |  |   <
|____/ \__|_|  \___|\__,_|_| |_| |_|_|  |_|\__,_|_|  |_|\_\
EOF
  echo -e "${RESET}${BOLD}  Local Streamer installer${RESET}"
}

banner

REPO_URL="${REPO_URL:-https://github.com/sAyaN24/local-streamer.git}"
BRANCH="main"
INSTALL_DIR="/opt/local-streamer"
SETUP_PUBLISHER=1
START_SERVICE=1
SERVICE_NAME="streammark"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --skip-publisher) SETUP_PUBLISHER=0; shift ;;
    --no-start) START_SERVICE=0; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ $EUID -eq 0 ]] || die "must be run as root (try: sudo bash $0)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The user who invoked sudo (falls back to root if run directly as root) --
# used to own the cloned repo so it stays editable without sudo afterwards.
TARGET_USER="${SUDO_USER:-root}"

step "1. OS check"
[[ -r /etc/os-release ]] || die "unsupported OS: /etc/os-release not found"
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}:${ID_LIKE:-}" in
  ubuntu*|debian*|*debian*) : ;;
  *) die "this installer targets Ubuntu/Debian only (detected: ${PRETTY_NAME:-unknown})" ;;
esac
log "Detected OS: ${PRETTY_NAME:-$ID}"

export DEBIAN_FRONTEND=noninteractive

step "2. Base packages"
log "Installing base packages (git, curl, ca-certificates, python3)..."
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg git lsb-release software-properties-common \
  python3 python3-venv python3-pip build-essential

step "3. Python >= 3.12 (backend-webserver/shared/stream-publisher require it)"
PYTHON_BIN=""
if command -v python3.12 &>/dev/null; then
  PYTHON_BIN=python3.12
elif python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
  PYTHON_BIN=python3
fi

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ "$ID" == "ubuntu" ]]; then
    log "System Python is older than 3.12; adding deadsnakes PPA for python3.12..."
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -y
    apt-get install -y python3.12 python3.12-venv python3.12-dev
    PYTHON_BIN=python3.12
  else
    warn "System Python is older than 3.12 and deadsnakes (Ubuntu-only) isn't" \
         "available on Debian. The native publisher venv step will be skipped;" \
         "the Docker-based services are unaffected (the image pins its own Python)."
    SETUP_PUBLISHER=0
  fi
fi
[[ -n "$PYTHON_BIN" ]] && log "Using $($PYTHON_BIN --version)"

step "4. Docker Engine + Compose plugin"
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  log "Docker + Compose plugin already installed ($(docker --version))"
else
  log "Installing Docker Engine + Compose plugin from Docker's apt repo..."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  ARCH="$(dpkg --print-architecture)"
  CODENAME="${VERSION_CODENAME:-$(lsb_release -cs)}"
  echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker

if [[ "$TARGET_USER" != "root" ]] && ! id -nG "$TARGET_USER" | grep -qw docker; then
  usermod -aG docker "$TARGET_USER"
  warn "added $TARGET_USER to the 'docker' group -- log out/in for that to take" \
       "effect on interactive shells (the systemd service below runs as root" \
       "and is unaffected)."
fi

DOCKER_BIN="$(command -v docker)"

# video group: lets the capture-card publisher (step 9 below) open /dev/videoN
# without running as root. Harmless/no-op if the group doesn't exist (no V4L2
# devices ever seen on this box) or the user is already in it.
if [[ "$SETUP_PUBLISHER" -eq 1 ]] && [[ "$TARGET_USER" != "root" ]] \
   && getent group video &>/dev/null && ! id -nG "$TARGET_USER" | grep -qw video; then
  usermod -aG video "$TARGET_USER"
  warn "added $TARGET_USER to the 'video' group -- log out/in for that to take" \
       "effect on interactive shells (the streammark-publisher systemd service" \
       "below runs as this user via systemd directly and is unaffected)."
fi

step "5. Clone or update the repo"
if [[ "$SETUP_PUBLISHER" -eq 1 ]]; then
  # Full clone: the native venv step below needs shared/ + stream-publisher/
  # source on disk.
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Repo already present at $INSTALL_DIR -- pulling latest $BRANCH..."
    # A previous --skip-publisher run on this box may have left the checkout
    # sparse (just infra/+install/). Disable that first so shared/+stream-
    # publisher/ (needed for the venv step below) actually land on disk --
    # otherwise `checkout`/`pull` below would silently keep them hidden even
    # though this run wants the full tree. Harmless no-op if not sparse.
    git -C "$INSTALL_DIR" sparse-checkout disable 2>/dev/null || true
    git -C "$INSTALL_DIR" fetch origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
  elif [[ -e "$INSTALL_DIR" ]]; then
    die "$INSTALL_DIR exists and isn't a git repo -- remove it or pass --dir <other path>"
  else
    log "Cloning $REPO_URL (branch $BRANCH) into $INSTALL_DIR..."
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  fi
else
  # --skip-publisher: this box only runs `docker compose up` against the
  # published GHCR images (see infra/docker-compose.yml's api/frontend
  # `image:`), so it never needs backend-webserver/frontend/stream-publisher/
  # shared source -- a shallow, blobless, sparse clone of just infra/ and
  # install/ is enough and is far smaller/faster than the whole repo.
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Repo already present at $INSTALL_DIR -- pulling latest $BRANCH (sparse: infra/, install/)..."
    git -C "$INSTALL_DIR" sparse-checkout set infra install 2>/dev/null || true
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
  elif [[ -e "$INSTALL_DIR" ]]; then
    die "$INSTALL_DIR exists and isn't a git repo -- remove it or pass --dir <other path>"
  else
    log "Sparse-cloning $REPO_URL (branch $BRANCH, infra/ + install/ only) into $INSTALL_DIR..."
    git clone --branch "$BRANCH" --depth 1 --filter=blob:none --sparse "$REPO_URL" "$INSTALL_DIR"
    git -C "$INSTALL_DIR" sparse-checkout set infra install
  fi
fi

if [[ "$TARGET_USER" != "root" ]]; then
  chown -R "$TARGET_USER":"$TARGET_USER" "$INSTALL_DIR"
fi

step "6. infra/.env"
ENV_FILE="$INSTALL_DIR/infra/.env"
ENV_EXAMPLE="$INSTALL_DIR/infra/.env.example"
if [[ ! -f "$ENV_FILE" ]]; then
  log "Creating infra/.env from infra/.env.example..."
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  warn "infra/.env still has the example LIVEKIT_API_SECRET / AUTH_JWT_SECRET" \
       "placeholder values -- edit $ENV_FILE and replace them before exposing" \
       "this box beyond localhost."
  [[ "$TARGET_USER" != "root" ]] && chown "$TARGET_USER":"$TARGET_USER" "$ENV_FILE"
else
  log "infra/.env already exists -- leaving secrets as-is, refreshing LAN IP below."
fi

# Migration: older versions of this script auto-set VITE_API_BASE_URL to this
# box's LAN IP. That's no longer needed (or wanted) now that the proxy service
# puts the frontend and API on the same origin -- and a leftover value here
# would silently override the frontend's same-origin default, pointing it at
# the no-longer-published :8000 instead. Comment it out if still present.
if grep -q '^VITE_API_BASE_URL=' "$ENV_FILE"; then
  sed -i 's|^VITE_API_BASE_URL=|#VITE_API_BASE_URL=|' "$ENV_FILE"
  log "Commented out a leftover VITE_API_BASE_URL in infra/.env (no longer needed -- see infra/README.md)."
fi

# Re-derive the LAN IP every run (not just on first creation) so a re-run of
# this script -- e.g. after a reboot changed the box's DHCP lease -- picks up
# an IP change automatically instead of silently going stale. Only
# LIVEKIT_URL needs it: browsers connect to LiveKit's WS/RTC signaling
# directly. The API URL doesn't -- the frontend defaults to same-origin
# /api/ (see frontend/src/api/client.js), reached through the proxy service
# (infra/docker/proxy.conf), so no IP needs to be baked in for it at all.
LAN_IP="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i !~ /^127\./) {print $i; exit}}')"
if [[ -n "$LAN_IP" ]]; then
  sed -i "s|LIVEKIT_URL=ws://[^:]*:7880|LIVEKIT_URL=ws://${LAN_IP}:7880|" "$ENV_FILE"
  sed -i "s|node_ip:.*|node_ip: ${LAN_IP}|" "$INSTALL_DIR/infra/docker/livekit.yaml" 2>/dev/null || true
  log "Set LiveKit LAN IP to $LAN_IP in infra/.env (edit it yourself if you'd rather pin a fixed hostname)."
fi

step "7. Native venv for the capture-card publisher (optional)"
if [[ "$SETUP_PUBLISHER" -eq 1 ]]; then
  log "Setting up native Python venv for stream-publisher (capture-card ingest)..."
  PUB_DIR="$INSTALL_DIR/stream-publisher"
  VENV_DIR="$PUB_DIR/.venv"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
  "$VENV_DIR/bin/pip" install --quiet -e "$INSTALL_DIR/shared" -e "$PUB_DIR"
  [[ "$TARGET_USER" != "root" ]] && chown -R "$TARGET_USER":"$TARGET_USER" "$VENV_DIR"
  log "Publisher venv ready at $VENV_DIR (run: $VENV_DIR/bin/streammark-ingest --room <name> --device /dev/video0)"
else
  log "Skipping publisher venv setup (--skip-publisher or Python 3.12 unavailable)."
fi

step "8. systemd service: Docker Compose stack"
log "Installing systemd service '$SERVICE_NAME'..."
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
TEMPLATE="$SCRIPT_DIR/streammark.service.template"
[[ -f "$TEMPLATE" ]] || TEMPLATE="$INSTALL_DIR/install/streammark.service.template"
[[ -f "$TEMPLATE" ]] || die "can't find streammark.service.template (looked next to $0 and in $INSTALL_DIR/install)"
sed \
  -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
  -e "s|__DOCKER_BIN__|$DOCKER_BIN|g" \
  "$TEMPLATE" > "$UNIT_PATH"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

if [[ "$START_SERVICE" -eq 1 ]]; then
  log "Starting $SERVICE_NAME (docker compose up -d)..."
  systemctl restart "$SERVICE_NAME"
  systemctl --no-pager status "$SERVICE_NAME" || true
else
  log "Skipped starting the service (--no-start). Edit $ENV_FILE, then run:" \
      "  sudo systemctl start $SERVICE_NAME"
fi

step "9. systemd service: capture-card publisher"
# Separate unit (not folded into the Docker stack's service above) because
# streammark-publish must run natively -- see the venv step's own comment.
# Restart=on-failure (set in the template) covers a capture card that isn't
# plugged in yet, or gets unplugged and replugged later: the process exits
# non-zero until a usable device shows up, and systemd just keeps retrying.
PUBLISHER_SERVICE_NAME="streammark-publisher"
if [[ "$SETUP_PUBLISHER" -eq 1 ]]; then
  log "Installing systemd service '$PUBLISHER_SERVICE_NAME'..."
  PUB_UNIT_PATH="/etc/systemd/system/${PUBLISHER_SERVICE_NAME}.service"
  PUB_TEMPLATE="$SCRIPT_DIR/streammark-publisher.service.template"
  [[ -f "$PUB_TEMPLATE" ]] || PUB_TEMPLATE="$INSTALL_DIR/install/streammark-publisher.service.template"
  if [[ -f "$PUB_TEMPLATE" ]]; then
    sed \
      -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
      -e "s|__TARGET_USER__|$TARGET_USER|g" \
      "$PUB_TEMPLATE" > "$PUB_UNIT_PATH"

    systemctl daemon-reload
    systemctl enable "$PUBLISHER_SERVICE_NAME"

    if [[ "$START_SERVICE" -eq 1 ]]; then
      log "Starting $PUBLISHER_SERVICE_NAME (retries automatically until a capture card is detected)..."
      systemctl restart "$PUBLISHER_SERVICE_NAME"
      systemctl --no-pager status "$PUBLISHER_SERVICE_NAME" || true
    else
      log "Skipped starting $PUBLISHER_SERVICE_NAME (--no-start). Start it with:" \
          "  sudo systemctl start $PUBLISHER_SERVICE_NAME"
    fi
  else
    warn "can't find streammark-publisher.service.template -- skipping the" \
         "capture-card publisher service (run streammark-publish by hand instead)."
    PUBLISHER_SERVICE_NAME=""
  fi
else
  log "Skipping publisher systemd service (--skip-publisher or Python 3.12 unavailable)."
  PUBLISHER_SERVICE_NAME=""
fi

step "10. Admin account"
# seed_admin.py prints the admin email/password to the 'seed-admin' container's own
# logs -- see infra/scripts/seed_admin.py. Wait for it to finish and pull those
# credentials out so this script can show them once, right here, instead of making
# every install dig through `docker compose logs`.
ADMIN_EMAIL_OUT=""
ADMIN_PASSWORD_OUT=""
if [[ "$START_SERVICE" -eq 1 ]]; then
  log "Re-running seed-admin (resetting the admin password so it can be shown here)..."
  # ADMIN_RESET=1: an admin always already exists on a re-run of this script, and
  # without this the backend's /auth/setup-admin would just 409 with nothing to show.
  # Scoped to ONLY this one explicit, manual invocation (shell-env prefix, never
  # written to infra/.env) -- see the ADMIN_RESET comments in docker-compose.yml and
  # seed_admin.py for why it must never default on for the routine `docker compose
  # up` a reboot triggers unattended via the streammark systemd service.
  # --force-recreate also guarantees a fresh run (and therefore fresh, trustworthy
  # logs below) regardless of whether compose already ran this container as part of
  # the main service restart above.
  (cd "$INSTALL_DIR/infra" && ADMIN_RESET=1 "$DOCKER_BIN" compose -f docker-compose.yml --env-file .env up -d --force-recreate seed-admin) \
    || warn "could not re-run the seed-admin container -- check it manually:" \
            "  docker compose -f $INSTALL_DIR/infra/docker-compose.yml logs seed-admin"

  log "Waiting for the seed-admin container to finish..."
  SEED_ADMIN_TIMEOUT=60
  SEED_ADMIN_ELAPSED=0
  while true; do
    SEED_ADMIN_STATUS="$(docker inspect --format '{{.State.Status}}' streammark-seed-admin 2>/dev/null || echo "missing")"
    [[ "$SEED_ADMIN_STATUS" == "exited" ]] && break
    if [[ "$SEED_ADMIN_ELAPSED" -ge "$SEED_ADMIN_TIMEOUT" ]]; then
      warn "timed out waiting for the seed-admin container -- check it manually:" \
           "  docker compose -f $INSTALL_DIR/infra/docker-compose.yml logs seed-admin"
      break
    fi
    sleep 2
    SEED_ADMIN_ELAPSED=$((SEED_ADMIN_ELAPSED + 2))
  done

  SEED_ADMIN_LOG="$(docker logs streammark-seed-admin 2>/dev/null || true)"
  ADMIN_EMAIL_OUT="$(sed -n 's/^ *email: *//p' <<<"$SEED_ADMIN_LOG" | tail -1)"
  ADMIN_PASSWORD_OUT="$(sed -n 's/^ *password: *//p' <<<"$SEED_ADMIN_LOG" | tail -1)"
else
  log "Skipping (--no-start) -- the admin account is created on first 'docker compose up'."
fi

log "Done."
DIVIDER="${CYAN}${BOLD}────────────────────────────────────────────────────────${RESET}"
echo -e "$DIVIDER"
echo -e "${BOLD}  Local Streamer (StreamMark) is ready${RESET}"
echo -e "$DIVIDER"
echo "  Install dir:  $INSTALL_DIR"
echo "  Env file:     $ENV_FILE"
echo "  Service:      systemctl {status|start|stop|restart} $SERVICE_NAME"
echo "  Logs:         docker compose -f $INSTALL_DIR/infra/docker-compose.yml logs -f"
echo "  Auto-restart: enabled (systemd starts it on boot; containers use restart: unless-stopped)"
if [[ -n "$PUBLISHER_SERVICE_NAME" ]]; then
  echo "  Publisher:    systemctl {status|start|stop|restart} $PUBLISHER_SERVICE_NAME"
  echo "  Pub. logs:    journalctl -u $PUBLISHER_SERVICE_NAME -f"
  echo "  Pub. restart: automatic -- retries every 10s until a capture card is detected"
fi
if [[ -n "$ADMIN_EMAIL_OUT" && -n "$ADMIN_PASSWORD_OUT" ]]; then
  echo -e "$DIVIDER"
  echo -e "${BOLD}${GREEN}  Admin login${RESET}"
  echo -e "    Email:    ${BOLD}${YELLOW}$ADMIN_EMAIL_OUT${RESET}"
  echo -e "    Password: ${BOLD}${YELLOW}$ADMIN_PASSWORD_OUT${RESET}"
  echo "    Log in, then open /admin to add further users."
  echo "    Note: every re-run of this script resets this password to a new"
  echo "    one (or back to ADMIN_PASSWORD in infra/.env, if you've pinned"
  echo "    it there) -- it only ever changes when you run setup.sh yourself,"
  echo "    never on an ordinary reboot."
else
  echo -e "$DIVIDER"
  echo "  Couldn't confirm the admin account/password this run -- check:"
  echo "    docker compose -f $INSTALL_DIR/infra/docker-compose.yml logs seed-admin"
fi
echo -e "$DIVIDER"
