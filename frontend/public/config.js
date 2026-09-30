// Placeholder read by src/api/client.js. The Docker image overwrites this
// file at container start (see docker/docker-entrypoint.d), generating it
// from the $API_BASE_URL env var passed to `docker run`/compose -- so one
// published image can point at whatever backend is reachable on the box
// it's deployed to, without rebuilding. Left empty here so local dev
// (`npm run dev`) and non-Docker builds fall back to VITE_API_BASE_URL.
window.__RUNTIME_CONFIG__ = {}
