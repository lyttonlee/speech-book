<template>
<!--FRAG:proofread-->
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import * as proofreadApi from '@/api/proofread'
import * as parseApi from '@/api/parse'
import * as voicesApi from '@/api/voices'
import type { ChapterNode, Segment } from '@/types'

/**
 * 三栏校对台（design/workspace.html §7 已解析章节）。
 *
 * 左：章节树（.chap-tree）｜中：片段列表（五维筛选 + 就地改）｜右：当前片段属性 + 情绪分布 + 待复核队列。
 * 所有改动即时 PATCH，后端写留痕；刷新本章只重拉本章，不做整页重载。
 */

const props = defineProps<{ workId: number }>()
const emit = defineEmits<{ synth: [] }>()

const store = useWorkStore()

// ---------------------------------------------------------------- 章节
/** 当前选中章节 id */
const activeChapterId = ref<number | null>(null)
/** 当前章节的段落（每段挂若干片段） */
const paragraphs = ref<Awaited<ReturnType<typeof proofreadApi.getProofread>>['paragraphs']>([])
/** 下拉用的角色（改说话人时选） */
const boardRoles = ref<Array<{ id: number; name: string; level: string }>>([])
const parsing = ref(false)

const activeChapter = computed<ChapterNode | null>(
  () => store.chapters.find((c) => c.id === activeChapterId.value) ?? null,
)
/** 当前章节的全部片段（按 order 拉平） */
const segments = computed<Segment[]>(() => paragraphs.value.flatMap((p) => p.segments ?? []))

// -------------------------------------------------------------- 五维筛选
const ftype = ref<'all' | 'narration' | 'dialogue' | 'psychology'>('all')
const fspeaker = ref('')
const femotion = ref('')
const onlyLow = ref(false)
const onlyEdited = ref(false)

const typeFilters = [
  { value: 'all', label: '全部' },
  { value: 'dialogue', label: '对话' },
  { value: 'narration', label: '叙述' },
  { value: 'psychology', label: '心理' },
] as const

const speakerOptions = computed(() => [...new Set(segments.value.map((s) => s.speaker_name).filter(Boolean) as string[])])
const emotionOptions = computed(() => [...new Set(segments.value.map((s) => s.emotion).filter(Boolean) as string[])])

const filteredSegments = computed(() => segments.value.filter((s) => {
  if (ftype.value !== 'all' && s.type !== ftype.value) return false
  if (fspeaker.value && s.speaker_name !== fspeaker.value) return false
  if (femotion.value && s.emotion !== femotion.value) return false
  if (onlyLow.value && !s.low_conf) return false
  if (onlyEdited.value && !isEdited(s.id)) return false
  return true
}))

function resetFilters() {
  ftype.value = 'all'
  fspeaker.value = ''
  femotion.value = ''
  onlyLow.value = false
  onlyEdited.value = false
}

// ---------------------------------------------------------------- 片段行
/** 被人工改过的片段 id 集合（橙色左边框 / 「仅人工改」筛选共用） */
const editedSegmentIds = computed(() => new Set(
  store.edits.filter((e) => e.object_type === 'segment' && e.object_id).map((e) => e.object_id as number),
))

/** 片段行样式：人工改过=橙左边框，低置信=红左边框（DESIGN_SPEC §7b.3） */
function segClass(s: Segment): string {
  if (s.low_conf) return 'lowconf'
  if (editedSegmentIds.value.has(s.id)) return 'edited'
  return ''
}

function isEdited(id: number): boolean {
  return editedSegmentIds.value.has(id)
}

/** 片段韵律摘要：由情绪 + 强度换算（与后端 EmotionIR 同一套口径） */
function prosodyOf(s: Segment): string {
  const k = (s.intensity - 50) / 100
  return `×${(1 + k * 0.3).toFixed(2)} ${k >= 0 ? '+' : ''}${(k * 4).toFixed(1)}st`
}

/** 当前操作的片段（右侧属性面板） */
const currentSegmentId = ref<number | null>(null)
const currentSegment = computed<Segment | null>(
  () => segments.value.find((s) => s.id === currentSegmentId.value) ?? null,
)

function selectSegment(s: Segment) {
  currentSegmentId.value = s.id
}

function chapterClass(c: ChapterNode): string {
  if (c.id === activeChapterId.value) return 'active'
  if (c.status === 'empty') return 'empty'
  if (c.low_conf_count) return 'unread'
  return 'done'
}

async function selectChapter(c: ChapterNode) {
  activeChapterId.value = c.id
  await loadChapter(c.id)
}

/** 加载某章的校对数据 */
async function loadChapter(chapterId: number) {
  const data = await proofreadApi.getProofread(props.workId, chapterId)
  paragraphs.value = data.paragraphs ?? []
  boardRoles.value = data.roles ?? []
  // 刷新后若原选中片段还在就保留选中，避免每改一次跳回第一条
  const still = segments.value.some((s) => s.id === currentSegmentId.value)
  if (!still) currentSegmentId.value = segments.value[0]?.id ?? null
}

/** 本章情绪分布：按情绪分组，柱宽按占比 */
const emotionDist = computed(() => {
  const map = new Map<string, number>()
  for (const s of segments.value) if (s.emotion) map.set(s.emotion, (map.get(s.emotion) ?? 0) + 1)
  const max = Math.max(1, ...map.values())
  return [...map.entries()]
    .map(([name, count]) => ({ name, count, pct: Math.round((count / max) * 100) }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
})

// ---------------------------------------------------------------- 片段编辑
/** 正在就地编辑文本的片段 id */
const editingId = ref<number | null>(null)
const editText = ref('')

/**
 * 片段改动统一入口：改完自动重拉本章片段 + 待复核队列。
 * store 的动作只刷新全景（指标 / 留痕 / 资产），片段明细得单独拉。
 */
async function withChapterReload(fn: () => Promise<unknown>) {
  await fn()
  if (activeChapterId.value) await loadChapter(activeChapterId.value)
  await loadReviewItems()
}

function startEditText(s: Segment) {
  editingId.value = s.id
  editText.value = s.text
  currentSegmentId.value = s.id
}

/** 保存正文：PATCH text 字段，后端写留痕 */
async function saveText(s: Segment) {
  if (editText.value.trim() === s.text) {
    editingId.value = null
    return
  }
  const text = editText.value.trim()
  editingId.value = null
  await withChapterReload(() => store.patchSegment(props.workId, s.id, { text }))
  ElMessage.success('已保存正文 · 已记入修改日志')
}

/** 改说话人（下拉） */
async function onChangeSpeaker(e: Event) {
  if (!currentSegment.value) return
  const val = (e.target as HTMLSelectElement).value
  const roleId = val ? Number(val) : null
  const role = boardRoles.value.find((r) => r.id === roleId)
  await withChapterReload(() => store.patchSegment(props.workId, currentSegment.value!.id, {
    speaker_role_id: roleId ?? undefined,
    speaker_name: role?.name ?? undefined,
  }))
  ElMessage.success('说话人已更新')
}

/** 改情绪（下拉） */
async function onChangeEmotion(e: Event) {
  if (!currentSegment.value) return
  const emotion = (e.target as HTMLSelectElement).value
  await withChapterReload(() => store.patchSegment(props.workId, currentSegment.value!.id, { emotion }))
  ElMessage.success('情绪已更新')
}

/** 改情绪强度（0~100，与后端字段口径一致） */
async function onChangeIntensity(e: Event) {
  if (!currentSegment.value) return
  const intensity = Number((e.target as HTMLInputElement).value)
  await withChapterReload(() => store.patchSegment(props.workId, currentSegment.value!.id, { intensity }))
}

/** 还原当前片段为 AI 原值 */
async function revertCurrent() {
  if (!currentSegment.value) return
  await withChapterReload(() => store.revertSegment(props.workId, currentSegment.value!.id, 'all'))
  ElMessage.success('已还原为 AI 原值')
}

/** 批量复核：把当前筛选出的低置信片段置信度拉满 */
async function batchReview() {
  const ids = filteredSegments.value.filter((s) => s.low_conf).map((s) => s.id)
  if (!ids.length) {
    ElMessage.info('当前筛选结果里没有低置信片段')
    return
  }
  await withChapterReload(() => store.batchPatchSegments(props.workId, ids, { confidence: 1 }))
  ElMessage.success(`已复核 ${ids.length} 条`)
}

/** 本章校对完成 → 通知父组件提交全本合成（合成入口在工作空间页，不在这里发请求） */
function submitChapter() {
  emit('synth')
}

// ---------------------------------------------------------------- 待复核队列
const reviewItems = ref<Array<{ segment_id: number; type: string; suggestion: string; confidence: number }>>([])

/** 拉全书的低置信片段（右侧「待复核队列」） */
async function loadReviewItems() {
  const res = await parseApi.getReviewItems(props.workId, true)
  reviewItems.value = res.items ?? []
}

/** 确认建议说话人：改说话人名 + 置信度拉满 */
async function confirmReview(it: { segment_id: number; suggestion: string }) {
  await withChapterReload(() => store.patchSegment(props.workId, it.segment_id, {
    speaker_name: it.suggestion,
    confidence: 1,
  }))
  ElMessage.success('已确认说话人')
}

// ---------------------------------------------------------------- 试听与导出
/**
 * 试听片段：POC 用该片段说话人绑定的音色即时合成一句。
 * 生产应直接播放该片段已合成的音频（assets 里按 segment 索引）。
 */
async function playSegment(s: Segment) {
  currentSegmentId.value = s.id
  const binding = store.bindings.find((b) => b.role_id === s.speaker_role_id)
  if (!binding?.voice_id) {
    ElMessage.warning('该说话人还没绑定音色，先去「角色与声纹绑定」')
    return
  }
  const res = await voicesApi.previewVoice(binding.voice_id, s.text.slice(0, 60))
  new Audio(res.audio_url).play().catch(() => ElMessage.warning('浏览器阻止了自动播放，请手动点击'))
}

/** 导出当前章节剧本：按「说话人：正文」拼成 TXT */
function exportScript() {
  const lines = segments.value.map((s) => (s.speaker_name ? `${s.speaker_name}：${s.text}` : s.text))
  const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `${store.currentWork?.name ?? 'work'}-script.txt`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * 供父组件在「重新解析 / 同步状态」后主动刷新。
 * 不传参数时沿用当前选中章节，传了则先切章节再拉。
 */
async function reload(chapterId?: number) {
  if (chapterId != null) activeChapterId.value = chapterId
  if (activeChapterId.value) await loadChapter(activeChapterId.value)
  await loadReviewItems()
}

defineExpose({ loadChapter, reload })
</script>
