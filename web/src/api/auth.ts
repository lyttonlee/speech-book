import http from './request'

export function register(email: string, password: string, nickname: string) {
  return http.post('/auth/register', { email, password, nickname })
}
export function login(email: string, password: string) {
  return http.post('/auth/login', { email, password })
}
export function me() {
  return http.get('/auth/me')
}
