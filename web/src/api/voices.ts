import http from './request'
import type { Voice, VoiceTag } from '@/types'

/**
 * 音色库接口（docs/接口文档.md §8 / §9）。
 * 注意：后端把 /clone 与 /tags 注册在 /{voice_id} 之前，
 * 因此这里不会出现 "clone" 被当成 id 的 422 冲突。
 */

/** 音色列表，支持标签交集检索与分类过滤 */
export function listVoices(params?: {
  tags?: string
  type?: 'builtin' | 'clone'
  mine?: boolean
  page?: number
  page_size?: number
}) {
  return http.get<{ items: Voice[]; total: number; page: number; page_size: number }>(
    '/voices', { params },
  )
}

export function getVoice(voiceId: number) {
  return http.get<Voice & { engine_voice_id: string; source: string; sample_rate: number }>(
    `/voices/${voiceId}`,
  )
}

/** 改音色名称 / 标签 */
export function updateVoice(voiceId: number, payload: { name?: string; tags?: string[] }) {
  return http.patch<Voice>(`/voices/${voiceId}`, payload)
}

/** 删除音色。被绑定引用时返回 { need_confirm: true, refs: n }，需带 force=true 二次确认 */
export function deleteVoice(voiceId: number, force = false) {
  return http.delete<{ need_confirm: boolean; refs: number; deleted: number | null; unbound: number }>(
    `/voices/${voiceId}`, { params: { force } },
  )
}

/** 生成试听音频（支持自定义文本与语速） */
export function previewVoice(voiceId: number, text?: string, speed = 1.0) {
  return http.post<{ audio_url: string; duration: number }>(
    `/voices/${voiceId}/preview`, { text, speed },
  )
}

// ------------------------------------------------------------ 音色标签

export function listTags(params?: { scope?: 'global' | 'work'; work_id?: number }) {
  return http.get<{ items: VoiceTag[]; total: number }>('/voices/tags', { params })
}

export function createTag(payload: {
  dim: string
  value: string
  group?: string
  scope?: 'global' | 'work'
  work_id?: number
  color?: string
}) {
  return http.post<{ id: number; dim: string; value: string }>('/voices/tags', payload)
}

/** 重命名 / 改配色 */
export function updateTag(tagId: number, payload: { value?: string; dim?: string; color?: string; group?: string }) {
  return http.patch<{ id: number; value: string; dim: string }>(`/voices/tags/${tagId}`, payload)
}

export function deleteTag(tagId: number) {
  return http.delete(`/voices/tags/${tagId}`)
}

// -------------------------------------------------------------- 声音克隆

/**
 * 提交声音克隆。前置合规：实名 + 授权书 + 声纹核验（本人）+ 公众人物关键词库。
 * 未通过时后端抛 422 CLONE_COMPLIANCE_FAILED / BANNED_PERSON。
 */
export function submitClone(name: string, consentDocUrl: string) {
  return http.post<{ task_id: string; voice_id: number; status: string }>('/voices/clone', {
    name,
    consent_doc_url: consentDocUrl,
  })
}

export function cloneStatus(taskId: string) {
  return http.get<{ status: string; progress: number; voice_id: number | null; reject_reason: string | null }>(
    `/voices/clone/${taskId}`,
  )
}

// ---------------------------------------------------------- 克隆合规前置

/** 实名认证（克隆前置 1/2） */
export function realnameVerify(payload: { real_name: string; id_card_no: string; consent_doc_url: string }) {
  return http.post<{ realname_verified: boolean; voiceprint_required: boolean }>(
    '/auth/realname', payload,
  )
}

/** 声纹核验（克隆前置 2/2，POC 免真实比对） */
export function voiceprintCheck() {
  return http.post<{ voiceprint_checked: boolean; poc_note?: string }>('/auth/voiceprint')
}
