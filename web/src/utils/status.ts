import type { WorkStatus } from '@/types'

/**
 * 作品状态机元数据（docs/接口文档.md §16.1 / DESIGN_SPEC §5.3）。
 * 集中在这里，避免各页面各写一套文案导致术语不一致。
 */
export interface StatusMeta {
  /** 英文状态值 */
  key: WorkStatus
  /** 中文展示名 */
  label: string
  /** 徽标样式类：ok=绿 / info=蓝 / warn=橙 / acc=紫 / 空=灰 */
  tone: 'ok' | 'info' | 'warn' | 'acc' | ''
}

export const STATUS_META: Record<WorkStatus, StatusMeta> = {
  draft: { key: 'draft', label: '草稿', tone: '' },
  text_uploaded: { key: 'text_uploaded', label: '文本已上传', tone: 'info' },
  parsing: { key: 'parsing', label: '解析中', tone: 'info' },
  pending_review: { key: 'pending_review', label: '待校对', tone: 'warn' },
  review_done: { key: 'review_done', label: '校对完成', tone: 'ok' },
  synthesizing: { key: 'synthesizing', label: '合成中', tone: 'info' },
  synth_done: { key: 'synth_done', label: '合成完成', tone: 'ok' },
  exporting: { key: 'exporting', label: '导出中', tone: 'info' },
  completed: { key: 'completed', label: '已完成', tone: 'ok' },
  archived: { key: 'archived', label: '已归档', tone: '' },
  deleted: { key: 'deleted', label: '已删除', tone: '' },
}

/** 状态 → 是否处于进行中（Dashboard「进行中」统计用） */
export const RUNNING_STATUSES: WorkStatus[] = ['parsing', 'synthesizing', 'exporting']

/** 状态 → 是否已合成完成（Dashboard「合成完成」统计用） */
export const SYNTH_DONE_STATUSES: WorkStatus[] = ['synth_done', 'exporting', 'completed']

/** 取状态元数据，未知状态回退成「草稿」样式，避免页面崩 */
export function statusMeta(status: WorkStatus | string): StatusMeta {
  return STATUS_META[status as WorkStatus] ?? STATUS_META.draft
}

/** 徽标类名：`<span class="badge ok">` */
export function statusBadgeClass(status: WorkStatus | string): string {
  const tone = statusMeta(status).tone
  return tone ? `badge ${tone}` : 'badge'
}

/**
 * 状态 → 流水线已完成段数（0~6），用于作品卡进度条的兜底估算。
 * 优先用后端给的 `summary.progress`，仅在缺失时才用它。
 */
export function stageIndex(status: WorkStatus | string): number {
  const map: Record<string, number> = {
    draft: 0,
    text_uploaded: 1,
    parsing: 1,
    pending_review: 2,
    review_done: 3,
    synthesizing: 4,
    synth_done: 5,
    exporting: 5,
    completed: 6,
  }
  return map[status] ?? 0
}

/** 片段类型 → 中文 + 徽标样式 */
export const SEGMENT_TYPE_META: Record<string, { label: string; tone: string }> = {
  narration: { label: '叙述', tone: 'info' },
  dialogue: { label: '对话', tone: 'acc' },
  psychology: { label: '心理', tone: 'warn' },
}

/** 关系类型 → 配色（与 design/assets/app.js 的 KIND_COLOR 保持一致） */
export const RELATION_KIND_COLOR: Record<string, string> = {
  narration: '#38bdf8',
  kinship: '#a78bfa',
  mate: '#34d399',
  other: '#fbbf24',
}

/** 秒 → `mm:ss` */
export function fmtDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/** 秒 → 「1 小时 20 分」这类粗略口播量，列表展示用 */
export function fmtDurationLoose(seconds: number): string {
  const mins = seconds / 60
  if (mins < 1) return '—'
  if (mins < 60) return `${Math.round(mins)} min`
  return `${(mins / 60).toFixed(1)} 小时`
}
