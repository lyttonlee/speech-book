import http from './request'
import type { Role, Voice } from '@/types'

/** 角色接口（docs/接口文档.md §7 / workspace.html 角色与声纹绑定区块） */

export function listRoles(workId: number, level?: string) {
  return http.get<{ items: Role[]; total: number }>(
    `/works/${workId}/roles`, { params: { level } },
  )
}

/** 新建角色（把「未知角色N」指派为新角色时用） */
export function createRole(workId: number, name: string, level = 'supporting') {
  return http.post<Role>(`/works/${workId}/roles`, { name, level })
}

/** 改角色名 / 画像 / 别名 / 级别（降为龙套走这里） */
export function updateRole(workId: number, roleId: number, payload: {
  name?: string
  level?: string
  aliases?: string[]
  profile?: Record<string, unknown>
}) {
  return http.patch<Role>(`/works/${workId}/roles/${roleId}`, payload)
}

/** 合并角色：把 source_role_ids 的台词改挂到目标角色 */
export function mergeRoles(workId: number, roleId: number, sourceRoleIds: number[]) {
  return http.post(`/works/${workId}/roles/${roleId}/merge`, { source_role_ids: sourceRoleIds })
}

/** 删除角色（破坏性操作，前端需二次确认） */
export function deleteRole(workId: number, roleId: number) {
  return http.delete(`/works/${workId}/roles/${roleId}`)
}

/** 角色台词统计 */
export function roleStats(workId: number, roleId: number) {
  return http.get<{ line_count: number; chapter_count: number; avg_sentence_len: number }>(
    `/works/${workId}/roles/${roleId}/stats`,
  )
}

/** 音色推荐 Top-N（按画像标签匹配） */
export function recommendVoices(workId: number, roleId: number, top = 5) {
  return http.get<{ items: Array<{ voice_id: number; name: string; score: number; matched_tags: string[] }> }>(
    `/works/${workId}/roles/${roleId}/recommend-voices`, { params: { top } },
  )
}

/** 取音色列表（绑定下拉用，带 usage_count） */
export function listVoicesForBind() {
  return http.get<{ items: Voice[] }>('/voices', { params: { page_size: 100 } })
}
