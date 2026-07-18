import { request } from './client.js'

export function signup({ email, password, name }) {
  return request('/auth/signup', { method: 'POST', body: { email, password, name } })
}

export function login({ email, password }) {
  return request('/auth/login', { method: 'POST', body: { email, password } })
}

export function getMe(token) {
  return request('/auth/me', { token })
}
