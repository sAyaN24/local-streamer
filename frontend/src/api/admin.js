import { request } from './client.js'

export function listUsers(token) {
  return request('/admin/users', { token })
}

export function createUser({ email, password, name, role }, token) {
  return request('/admin/users', { method: 'POST', body: { email, password, name, role }, token })
}
