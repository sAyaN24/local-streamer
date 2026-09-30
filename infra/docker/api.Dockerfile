# Build context is the repo root (see infra/docker-compose.yml's api service),
# since this image needs both shared/ and backend-webserver/ as siblings.
FROM python:3.12-slim AS base

WORKDIR /app

COPY shared/ ./shared/
COPY backend-webserver/pyproject.toml backend-webserver/README.md ./backend-webserver/
COPY backend-webserver/src/ ./backend-webserver/src/

RUN pip install --no-cache-dir ./shared ./backend-webserver

ENV API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz',timeout=2).status==200 else 1)"

CMD ["streammark-api"]
