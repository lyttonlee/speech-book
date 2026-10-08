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
/** 刷新令牌（POC 直接用当前凭证重签，生产走 refresh_token） */
export function refresh(refreshToken = '') {
  return http.post<{ access_token: string }>('/auth/refresh', { refresh_token: refreshToken })
}
/** 改基本资料（昵称），邮箱作为登录标识不允许改 */
export function updateMe(payload: { nickname?: string }) {
  return http.patch('/auth/me', payload)
}

/** 修改密码：需先校验当前密码 */
export function changePassword(payload: { old_password: string; new_password: string }) {
  return http.post<{ changed: boolean }>('/auth/password', payload)
}

export function logout() {
  return http.post('/auth/logout')
}
