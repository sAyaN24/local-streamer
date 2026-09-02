# --- build: installs deps and produces the static bundle; discarded after this stage ---
FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines VITE_* vars into the bundle at build time, not read at container runtime --
# override via `docker build --build-arg VITE_API_BASE_URL=https://api.example.com` when
# building for anything other than a same-host backend on :8000.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# --- final: just the static output behind nginx, no node/npm/build toolchain ---
FROM nginx:alpine AS final
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5173
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:5173/ || exit 1
