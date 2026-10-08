import http from './request'
import type { Segment, SegmentPatch } from '@/types'

/**
 * 校对工作台接口（workspace.html 已解析章节区块）。
 * 前端约定：每次操作即时 PATCH（FR-808），后端幂等写字段 + 写修改留痕。
 */

/** 三栏校对数据：章节 / 片段明细 / 角色 / 音色 */
export function getProofread(workId: number, chapterId?: number) {
  return http.get<{
    chapter: { id: number; title: string; order: number } | null
    paragraphs: Array<{ id: number; order: number; text: string; segments: Segment[] }>
    roles: Array<{ id: number; name: string; level: string }>
    voices: Array<{ id: number; name: string }>
  }>(`/works/${workId}/proofread`, { params: { chapter_id: chapterId } })
}

/** 改单个片段（类型 / 说话人 / 情绪 / 强度 / 正文） */
export function patchSegment(workId: number, segmentId: number, patch: SegmentPatch) {
  return http.patch<{ segment: Segment; changes: number }>(
    `/works/${workId}/segments/${segmentId}`, patch,
  )
}

/** 批量改多个片段（前端批量操作栏） */
export function batchPatchSegments(workId: number, ids: number[], patch: SegmentPatch) {
  return http.post<{ applied: number; total: number; failed: number[] }>(
    `/works/${workId}/segments/batch`, { ids, patch },
  )
}

/** 把片段还原到 AI 原值（field 传 'all' 表示全部字段） */
export function revertSegment(workId: number, segmentId: number, field = 'all') {
  return http.post<{ segment: Segment; reverted: string[] }>(
    `/works/${workId}/segments/${segmentId}/revert`, { field },
  )
}

/** 待复核队列：只拉低置信片段，供右侧「待复核」列表优先处理 */
export function getReviewItems(workId: number, type?: string, lowConfOnly = true) {
  return http.get<{ items: Array<{ segment_id: number; type: string; suggestion: string; confidence: number }> }>(
    `/works/${workId}/parse/review-items`,
    { params: { type, low_conf_only: lowConfOnly } },
  )
}

/** 片段维度的修订历史（撤销 / 重做依据） */
export function getSegmentEdits(workId: number, segmentId?: number) {
  return http.get<{ items: Array<{ field: string; old_value: string | null; new_value: string | null; created_at: string }>; total: number }>(
    `/works/${workId}/proofread/edits`, { params: { segment_id: segmentId } },
  )
}
