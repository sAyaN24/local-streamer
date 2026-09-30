#!/bin/sh
# Runs automatically via nginx's own /docker-entrypoint.sh (which sources
# every *.sh in this directory before starting nginx). Regenerates config.js
# from $API_BASE_URL at container start, so the same published image works
# on any LAN -- pass it via `docker run -e API_BASE_URL=http://<box-ip>:8000`
# or the frontend service's `environment:` in docker-compose.yml. Left
# untouched (falling back to the value baked in at build time) when unset.
set -eu

CONFIG_FILE=/usr/share/nginx/html/config.js

if [ -n "${API_BASE_URL:-}" ]; then
  ESCAPED=$(printf '%s' "$API_BASE_URL" | sed 's/\\/\\\\/g; s/"/\\"/g')
  cat > "$CONFIG_FILE" <<EOF
window.__RUNTIME_CONFIG__ = {
  API_BASE_URL: "${ESCAPED}"
}
EOF
  echo "entrypoint: wrote API_BASE_URL=${API_BASE_URL} to config.js"
fi
