import { request } from './client.js'

export function listRooms() {
  return request('/rooms')
}

export function getViewerToken(roomId, { identity, name } = {}) {
  return request(`/rooms/${encodeURIComponent(roomId)}/token`, { params: { identity, name } })
}

export function getBroadcasterToken(roomId, authToken) {
  return request(`/rooms/${encodeURIComponent(roomId)}/broadcaster-token`, { token: authToken })
}

export function getAnnotationHistory(roomId) {
  return request(`/rooms/${encodeURIComponent(roomId)}/annotations`)
}
