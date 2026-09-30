import http from './request'
import type { Binding } from '@/types'

// GET /works/{id}/bindings
export function listBindings(workId: number) {
  return http.get(`/works/${workId}/bindings`)
}

// PUT /works/{id}/bindings  —— body: { items: [{ role_id, voice_id, params }] }
// role_id=0 表示旁白(narrator)
export function setBindings(workId: number, items: Binding[]) {
  return http.put(`/works/${workId}/bindings`, { items })
}

// POST /works/{id}/bindings/auto —— 后端按音色标签自动绑定
export function autoBind(workId: number) {
  return http.post(`/works/${workId}/bindings/auto`)
}
