<template>
  <div class="grid" style="grid-template-columns: 1fr 1.6fr">
    <!-- ============ 左：解析进度 + 需要复核 ============ -->
    <div class="col gap-4">
      <div class="panel">
        <div class="card-h">
          <h3>解析进度</h3>
          <span :class="['badge', parseDone ? 'ok' : 'info']">
            <span class="dot"></span>{{ parseDone ? '完成' : '进行中' }}
          </span>
        </div>

        <div class="progress mb"><i :style="{ width: progress + '%' }"></i></div>
        <div class="row between tiny muted">
          <span>{{ stage || '分章 → 分段 → 说话人识别 → 情绪标注' }}</span>
          <span class="mono">{{ progress }}%</span>
        </div>

        <hr class="divider" />

        <div class="grid cols-2 gap-3">
          <div class="stat"><span class="k">章节</span><span class="v">{{ stats.chapters }}</span></div>
          <div class="stat"><span class="k">片段</span><span class="v">{{ stats.segments }}</span></div>
          <div class="stat"><span class="k">角色</span><span class="v">{{ stats.roles }}</span></div>
          <div class="stat">
            <span class="k">低置信</span>
            <span class="v" :style="{ color: stats.lowConf ? 'var(--warn)' : '' }">{{ stats.lowConf }}</span>
          </div>
        </div>

        <!-- 单段试听：拿说话人当前绑定的音色实时合成一小段，POC 为 tone 占位 -->
        <div v-if="previewUrl" class="mt">
          <audio :src="previewUrl" controls style="width: 100%"></audio>
        </div>
      </div>

      <div class="panel">
        <div class="card-h">
          <h3>需要复核</h3><span class="sub">说话人置信度低</span>
        </div>
        <div
          v-for="it in reviewItems" :key="it.segment_id"
          class="card mt-2"
          :style="it.confidence < 0.5 ? 'border-color:rgba(251,191,36,0.35)' : ''"
        >
          <p class="sm">「{{ trim(quote(it)) }}」</p>
          <div class="row mt-2">
            <span class="badge warn"><span class="dot"></span>疑似 {{ it.suggestion }}</span>
            <button class="btn btn-sm right" @click="confirmReview(it)">确认</button>
          </div>
        </div>
        <p v-if="!reviewItems.length" class="hint">全部片段置信度达标，无需人工复核。</p>
      </div>
    </div>

    <!-- ============ 右：片段明细（可筛选 / 可改） ============ -->
    <div class="panel" style="padding: 0; overflow: hidden">
      <div class="card-h" style="padding: 18px 20px 0">
        <h3>片段明细</h3>
        <span class="sub">{{ currentChapterTitle }} · 共 {{ segments.length }} 段</span>
      </div>

      <!-- 工具条：类型分段筛选 + 内容搜索 + 导出剧本 -->
      <div class="row between wrap gap-3" style="padding: 12px 20px">
        <div class="segmented" style="padding: 3px">
          <button :class="{ active: ftype === 'all' }" @click="ftype = 'all'">全部</button>
          <button :class="{ active: ftype === 'dialogue' }" @click="ftype = 'dialogue'">对话</button>
          <button :class="{ active: ftype === 'narration' }" @click="ftype = 'narration'">叙述</button>
          <button :class="{ active: ftype === 'psychology' }" @click="ftype = 'psychology'">心理</button>
        </div>
        <div class="row gap-2">
          <div class="search" style="width: 190px">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" />
            </svg>
            <input v-model="keyword" class="input" placeholder="搜索片段内容…" />
          </div>
          <button class="btn btn-sm" @click="exportScript">导出剧本</button>
        </div>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th style="width: 52px">#</th><th>内容</th><th style="width: 92px">类型</th>
            <th style="width: 88px">说话人</th><th style="width: 124px">情绪</th><th style="width: 74px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in filteredSegments" :key="s.id">
            <td class="mono">{{ pad(s.order) }}</td>
            <td>{{ s.text }}</td>
            <td class="cell-type"><span :class="typeBadge(s.type)">{{ typeLabel(s.type) }}</span></td>
            <td>{{ s.speaker_name || '—' }}</td>
            <td><span class="badge">{{ s.emotion || '平静' }} · {{ s.intensity }}</span></td>
            <td class="right" style="white-space: nowrap">
              <button class="icon-btn" title="试听本段" @click="playSegment(s)">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
              </button>
              <button class="icon-btn" title="修正说话人" @click="editSpeaker(s)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z" />
                </svg>
              </button>
            </td>
          </tr>
          <tr v-if="!segments.length">
            <td colspan="6" class="hint" style="text-align: center; padding: 40px 0">
              还没有解析结果，点下方「↻ 重新解析」再跑一次
            </td>
          </tr>
        </tbody>
      </table>

      <div class="row between wrap gap-3" style="padding: 14px 20px">
        <span class="tiny muted">情绪含强度 0-1 · 行内 ▶ 可试听单段 / ✎ 修正说话人</span>
        <div class="row gap-2">
          <button class="btn" :loading="reparsing" @click="reparse">↻ 重新解析</button>
          <button class="btn btn-primary" @click="emit('next')">确认无误，去绑定 →</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import { useTaskSSE } from '@/composables/useSSE'
import * as proofreadApi from '@/api/proofread'
import * as parseApi from '@/api/parse'
import * as worksApi from '@/api/works'
import * as voicesApi from '@/api/voices'
import { SEGMENT_TYPE_META } from '@/utils/status'
import type { Segment } from '@/types'

/**
 * 步骤二「解析确认」（design/studio.html §步骤 2）。
 *
 * 三块内容：解析进度 + 待复核队列（左）、片段明细表（右，可筛选 / 试听 / 改说话人）。
 * 人工确认说话人或改完文本都会走 PATCH 接口，落修改留痕，所以本步可直接「确认无误」进入下一步。
 */

const props = defineProps<{ workId: number }>()
const emit = defineEmits<{ next: [] }>()

const store = useWorkStore()

// ---------------------------------------------------------------- 数据
type ReviewItem = {
  segment_id: number
  type: string
  suggestion: string
  confidence: number
}

const segments = ref<Segment[]>([])
const reviewItems = ref<ReviewItem[]>([])
/** 当前章节标题（.card-h 的副标题用） */
const currentChapterTitle = ref('第 1 章')
const reparsing = ref(false)
const previewUrl = ref('')

// -------------------------------------------------------------- 筛选
/** 类型筛选：all | narration | dialogue | psychology */
const ftype = ref<'all' | 'narration' | 'dialogue' | 'psychology'>('all')
const keyword = ref('')

const filteredSegments = computed(() => segments.value.filter((s) => {
  if (ftype.value !== 'all' && s.type !== ftype.value) return false
  if (keyword.value && !s.text.includes(keyword.value)) return false
  return true
}))

/** 四格统计：章节 / 片段 / 角色 / 低置信 */
const stats = computed(() => ({
  chapters: new Set(segments.value.map((s) => s.chapter_id)).size,
  segments: segments.value.length,
  roles: new Set(segments.value.map((s) => s.speaker_name).filter(Boolean)).size,
  lowConf: segments.value.filter((s) => s.low_conf).length,
}))

// ---------------------------------------------------------------- 工具
function typeLabel(type: string) {
  return SEGMENT_TYPE_META[type]?.label ?? type
}
function typeBadge(type: string) {
  const tone = SEGMENT_TYPE_META[type]?.tone ?? ''
  return tone ? `badge ${tone}` : 'badge'
}
/** 序号补零，和设计稿里的 01 / 02 对齐 */
function pad(n: number) {
  return String(n).padStart(2, '0')
}
function trim(v: string) {
  return v.length > 26 ? `${v.slice(0, 26)}…` : v
}
/** 复核卡片里展示的原文：从当前片段表里反查片段正文 */
function quote(it: ReviewItem) {
  const s = segments.value.find((x) => x.id === it.segment_id)
  return s?.text ?? ''
}

// -------------------------------------------------------------- 列表加载
/**
 * 拉一次「章节 + 片段 + 待复核」。
 * 解析任务刚结束时由 watch 触发，手动改完片段也走这里刷新。
 */
async function load() {
  const [pf, rv, roles] = await Promise.all([
    proofreadApi.getProofread(props.workId),
    proofreadApi.getReviewItems(props.workId),
    parseApi.getRoles(props.workId),
  ])
  segments.value = (pf.paragraphs ?? []).flatMap((p) => p.segments ?? [])
  reviewItems.value = (rv.items ?? []).filter((i) => i.suggestion)
  store.setSegments(segments.value)
  store.setRoles(roles.items ?? [])
  if (pf.chapter?.title) currentChapterTitle.value = pf.chapter.title
}

/** 按当前绑定音色实时合成一段试听（POC 为 tone 占位音） */
async function playSegment(s: Segment) {
  const role = store.roles.find((r) => r.name === s.speaker_name)
  if (!role) return ElMessage.info('该片段还没有说话人绑定，去音色库选一个再试听')
  const res = await voicesApi.previewVoice(role.bound_voice_id ?? 1, s.text)
  previewUrl.value = res.audio_url
}

/** ✎ 修正说话人：弹窗输入新名字，PATCH 到片段上 */
async function editSpeaker(s: Segment) {
  try {
    const { value } = await ElMessageBox.prompt('修正这个片段的说话人', '修正说话人', {
      inputValue: s.speaker_name ?? '',
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    const name = String(value).trim()
    if (!name) return
    await proofreadApi.patchSegment(props.workId, s.id, { speaker_name: name })
    ElMessage.success('已保存并留痕')
    await load()
  } catch {
    /* 用户取消弹窗不视为错误 */
  }
}

/** 「确认」复核项：把该片段的说话人直接改成系统建议值 */
async function confirmReview(it: ReviewItem) {
  await proofreadApi.patchSegment(props.workId, it.segment_id, { speaker_name: it.suggestion })
  ElMessage.success('已确认说话人')
  await load()
}

/** 导出剧本：把当前筛选结果拼成 TXT 下载 */
function exportScript() {
  const body = filteredSegments.value
    .map((s) => `${pad(s.order)}　${s.speaker_name ? `【${s.speaker_name}】` : ''}${s.text}`)
    .join('\n')
  download(`${store.currentWork?.name ?? 'work'}-剧本.txt`, body)
}

/** 下载工具：前端 Blob 直出，不占用后端存储 */
function download(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// --------------------------------------------------------- 重新解析（SSE）
const parseTaskId = ref('')
// 解构到顶层：模板里可直接用 parseDone / progress / stage，不必写 .value
const { progress, stage, done: parseDone, connect, close } = useTaskSSE(parseTaskId)

/** 重跑解析：先存文本（避免编辑器内容丢失），再起任务并订阅进度 */
async function reparse() {
  const text = (await worksApi.getText(props.workId))?.content
  if (text) await worksApi.mergeText(props.workId, 'novel.txt', text)
  reparsing.value = true
  const r = await parseApi.startParse(props.workId)
  parseTaskId.value = r.task_id
  progress.value = 0
  connect()
}

// 解析成功 → 重拉一次片段与复核队列；进度条满格停在完成态
watch(parseDone, async (v) => {
  if (!v) return
  reparsing.value = false
  close()
  await load()
})

onMounted(async () => {
  await load()
  if (progress.value === 0) progress.value = 100
})

defineExpose({ reparse })
</script>
