import http from './request'
import type { AudioAsset, OverviewData, PipelineStage, Work, WorkStatus } from '@/types'

// ------------------------------------------------------------ 作品 CRUD

export function listWorks(params?: { status?: WorkStatus; keyword?: string; page?: number; page_size?: number }) {
  return http.get<{ items: Work[]; total: number; page: number; page_size: number }>('/works', { params })
}

export function createWork(payload: { name: string; author?: string; type?: string; intro?: string; lang?: string }) {
  return http.post<Work>('/works', payload)
}

export function getWork(workId: number) {
  return http.get<Work>(`/works/${workId}`)
}

export function updateWork(workId: number, payload: Partial<Pick<Work, 'name' | 'author' | 'intro' | 'type' | 'cover_url'>>) {
  return http.patch<Work>(`/works/${workId}`, payload)
}

/** 删除进回收站（30 天），可 restore 恢复 */
export function deleteWork(workId: number) {
  return http.delete(`/works/${workId}`)
}

/** 从回收站恢复 */
export function restoreWork(workId: number) {
  return http.post<Work>(`/works/${workId}/restore`)
}

/** 复制作品（可复用角色绑定与合成参数） */
export function duplicateWork(workId: number, reuseBindings = true, reuseParams = true) {
  return http.post<Work>(`/works/${workId}/duplicate`, {
    reuse_bindings: reuseBindings,
    reuse_params: reuseParams,
  })
}

// ------------------------------------------------------------ 文本与章节

export function mergeText(workId: number, filename: string, content: string) {
  return http.post(`/works/${workId}/files/merge`, { filename, content })
}

export function getText(workId: number) {
  return http.get(`/works/${workId}/files/text`)
}

export function patchChapter(workId: number, chapterId: number, payload: { title?: string; order?: number }) {
  return http.patch(`/works/${workId}/chapters/${chapterId}`, payload)
}

/** 增量追加章节（不影响已合成部分） */
export function appendChapter(workId: number, title: string, content: string) {
  return http.post(`/works/${workId}/files/append`, { title, content })
}

// ------------------------------------------------------- 工作空间全景

/**
 * 取工作空间首屏所需的全部数据（一次请求，避免前端发十几个接口拼页面）。
 * 含：作品头 / 六段流水线 / 六项指标 / 角色与绑定 / 合规前置 /
 *     关系图 / 章节树 / 音频资产 / 修改留痕 / 版本快照
 */
export function getOverview(workId: number) {
  return http.get<OverviewData>(`/works/${workId}/overview`)
}

/** 只刷新流水线六段状态与耗时（轮询时用，比 overview 轻） */
export function getPipeline(workId: number) {
  return http.get<{ items: PipelineStage[]; total: number }>(`/works/${workId}/pipeline`)
}

// ------------------------------------------------------------ 音频资产

export function listAssets(workId: number, kind?: string) {
  return http.get<{ items: AudioAsset[]; total: number }>(`/works/${workId}/assets`, { params: { kind } })
}

/** 扫描历史合成任务补齐资产（幂等，列表与真实产物不同步时兜底） */
export function reindexAssets(workId: number) {
  return http.get<{ added: number; total: number }>(`/works/${workId}/assets/reindex`)
}

// ---------------------------------------------------------------- 统计

export function getStats(workId: number) {
  return http.get(`/works/${workId}/stats`)
}

export function getAnalysis(workId: number) {
  return http.get(`/works/${workId}/analysis`)
}
