# --- build: installs deps and produces the static bundle; discarded after this stage ---
FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines VITE_* vars into the bundle at build time, not read at container runtime.
# Left empty by default: src/api/client.js then falls back to same-origin /api/ at
# runtime, which is correct when served through the proxy service (see
# infra/docker/proxy.conf) -- no LAN IP needs to be baked in at all. Override via
# `docker build --build-arg VITE_API_BASE_URL=https://api.example.com` only if the
# API is genuinely hosted somewhere other than this same origin's /api/.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# --- final: just the static output behind nginx, no node/npm/build toolchain ---
FROM nginx:alpine AS final
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
# Picked up automatically by nginx's own /docker-entrypoint.sh (runs every
# *.sh here before starting nginx) -- regenerates config.js from $API_BASE_URL
# at container start so this image needs no rebuild per deployment/LAN.
COPY docker/docker-entrypoint.d/20-generate-runtime-config.sh /docker-entrypoint.d/20-generate-runtime-config.sh
RUN chmod +x /docker-entrypoint.d/20-generate-runtime-config.sh
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5173
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:5173/ || exit 1
