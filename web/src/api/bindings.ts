import http from './request'
import type { Binding } from '@/types'

// GET /works/{id}/bindings
// 返回「角色 id → 音色 id」的映射表，绑定与否都用 voice_id=null 占位
export function listBindings(workId: number) {
  return http.get<{ items: Binding[] }>(`/works/${workId}/bindings`)
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
