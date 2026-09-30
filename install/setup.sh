#!/usr/bin/env bash
# Bootstraps a fresh Ubuntu/Debian box to run Local Streamer (StreamMark):
# installs Docker + the Python toolchain, clones/updates the repo, and
# installs a systemd service so the Docker Compose stack (LiveKit + MongoDB +
# API + frontend) comes up automatically on boot and stays up via Docker's
# own `restart: unless-stopped` policy.
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
#                        needed if this box has the capture hardware attached
#   --no-start           Install everything but don't start the service yet
#                        (use this if you still need to edit infra/.env)
#
# Safe to re-run: pulls the latest commit on $BRANCH instead of re-cloning,
# and re-installs the systemd unit idempotently.

set -euo pipefail

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

log() { echo -e "\n==> $*"; }
warn() { echo -e "\n!! $*" >&2; }
die() { echo -e "\nError: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "must be run as root (try: sudo bash $0)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The user who invoked sudo (falls back to root if run directly as root) --
# used to own the cloned repo so it stays editable without sudo afterwards.
TARGET_USER="${SUDO_USER:-root}"

# ── 1. OS check ────────────────────────────────────────────────────────────
[[ -r /etc/os-release ]] || die "unsupported OS: /etc/os-release not found"
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}:${ID_LIKE:-}" in
  ubuntu*|debian*|*debian*) : ;;
  *) die "this installer targets Ubuntu/Debian only (detected: ${PRETTY_NAME:-unknown})" ;;
esac
log "Detected OS: ${PRETTY_NAME:-$ID}"

export DEBIAN_FRONTEND=noninteractive

# ── 2. Base packages ──────────────────────────────────────────────────────
log "Installing base packages (git, curl, ca-certificates, python3)..."
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg git lsb-release software-properties-common \
  python3 python3-venv python3-pip build-essential

# ── 3. Python >= 3.12 (backend-webserver/shared/stream-publisher require it) ─
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

# ── 4. Docker Engine + Compose plugin (official apt repo) ────────────────
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

# ── 5. Clone or update the repo ───────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  log "Repo already present at $INSTALL_DIR -- pulling latest $BRANCH..."
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
elif [[ -e "$INSTALL_DIR" ]]; then
  die "$INSTALL_DIR exists and isn't a git repo -- remove it or pass --dir <other path>"
else
  log "Cloning $REPO_URL (branch $BRANCH) into $INSTALL_DIR..."
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

if [[ "$TARGET_USER" != "root" ]]; then
  chown -R "$TARGET_USER":"$TARGET_USER" "$INSTALL_DIR"
fi

# ── 6. infra/.env ──────────────────────────────────────────────────────────
ENV_FILE="$INSTALL_DIR/infra/.env"
ENV_EXAMPLE="$INSTALL_DIR/infra/.env.example"
if [[ ! -f "$ENV_FILE" ]]; then
  log "Creating infra/.env from infra/.env.example..."
  cp "$ENV_EXAMPLE" "$ENV_FILE"

  LAN_IP="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i !~ /^127\./) {print $i; exit}}')"
  if [[ -n "$LAN_IP" ]]; then
    sed -i "s|LIVEKIT_URL=ws://[^:]*:7880|LIVEKIT_URL=ws://${LAN_IP}:7880|" "$ENV_FILE"
    sed -i "s|node_ip:.*|node_ip: ${LAN_IP}|" "$INSTALL_DIR/infra/docker/livekit.yaml" 2>/dev/null || true
    log "Set LiveKit LAN IP to $LAN_IP in infra/.env (override later if this box's IP changes)."
  fi

  warn "infra/.env still has the example LIVEKIT_API_SECRET / AUTH_JWT_SECRET" \
       "placeholder values -- edit $ENV_FILE and replace them before exposing" \
       "this box beyond localhost."
  [[ "$TARGET_USER" != "root" ]] && chown "$TARGET_USER":"$TARGET_USER" "$ENV_FILE"
else
  log "infra/.env already exists -- leaving it as-is."
fi

# ── 7. Native venv for the capture-card publisher (optional) ─────────────
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

# ── 8. systemd service ─────────────────────────────────────────────────────
log "Installing systemd service '$SERVICE_NAME'..."
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
sed \
  -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
  -e "s|__DOCKER_BIN__|$DOCKER_BIN|g" \
  "$SCRIPT_DIR/streammark.service.template" > "$UNIT_PATH"

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

log "Done."
echo "  Install dir:  $INSTALL_DIR"
echo "  Env file:     $ENV_FILE"
echo "  Service:      systemctl {status|start|stop|restart} $SERVICE_NAME"
echo "  Logs:         docker compose -f $INSTALL_DIR/infra/docker-compose.yml logs -f"
echo "  Auto-restart: enabled (systemd starts it on boot; containers use restart: unless-stopped)"
