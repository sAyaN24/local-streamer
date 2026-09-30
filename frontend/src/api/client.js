// Runtime config (window.__RUNTIME_CONFIG__, from public/config.js) wins when
// present -- it's how the Docker image gets its API URL without a rebuild.
// Then the build-time Vite env var, for local dev / non-Docker builds. If
// neither is set, default to same-origin /api -- the proxy service (see
// infra/docker/proxy.conf) puts the frontend and API on the same origin, so
// no LAN IP needs to be known or configured at all.
// Always ends in '/' and request() always strips path's leading '/' before
// combining: a leading '/' in the second arg to `new URL()` resolves against
// the base's ORIGIN, not its path, which would silently drop a /api prefix.
const BASE_URL = withTrailingSlash(
  window.__RUNTIME_CONFIG__?.API_BASE_URL ||
    import.meta.env.VITE_API_BASE_URL ||
    `${window.location.origin}/api/`,
)

function withTrailingSlash(url) {
  return url.endsWith('/') ? url : `${url}/`
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export async function request(path, { method = 'GET', body, token, params } = {}) {
  const url = new URL(path.replace(/^\/+/, ''), BASE_URL)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value)
      }
    }
  }

  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.')
  }

  if (response.status === 204) return null

  const text = await response.text()
  const data = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw new ApiError(response.status, data?.detail ?? response.statusText)
  }

  return data
}
