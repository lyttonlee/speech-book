<template>
<!--FRAG:audio-->
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import { useTaskSSE } from '@/composables/useSSE'
import * as synthApi from '@/api/synth'
import { fmtSize, mkBars } from '@/utils/format'
import type { AudioAsset } from '@/types'

/**
 * 已制作配音（design/workspace.html §8）。
 *
 * 双色分角色轨播放器 + 音频资产表 + 重合成面板；
 * 合成进度走 SSE（docs/接口文档.md §12.3），完成后自动刷新资产。
 */

const props = defineProps<{ workId: number }>()

const store = useWorkStore()

// ---------------------------------------------------------------- 合成
const synthing = ref(false)
/** 合成任务 id（SSE 订阅与轮询状态都用它） */
const taskId = ref('')
/** 合成耗时（本地计时，仅展示） */
const synthElapsed = ref(0)
let timer: number | undefined

// SSE 进度订阅，解构成顶层 ref：模板里可直接用 sseProgress / sseStage / sseDone
const {
  progress: sseProgress, stage: sseStage, done: sseDone, connect: sseConnect, close: sseClose,
} = useTaskSSE(() => taskId.value)

/** 发起合成：scope=sample 样章 / full 全本 / range 受影响片段 */
async function startSynth(scope: 'sample' | 'full' | 'range') {
  synthing.value = true
  try {
    const res = await synthApi.startSynth(props.workId, scope) as { task_id?: string; id?: string }
    taskId.value = res.task_id ?? res.id ?? ''
    if (taskId.value) {
      synthElapsed.value = 0
      timer = window.setInterval(() => { synthElapsed.value += 1 }, 1000)
      sseConnect()
      ElMessage.success('合成任务已提交')
    }
  } finally {
    synthing.value = false
  }
}

/** SSE 完成后刷新资产与流水线；同时停掉本地计时 */
watch(sseDone, async (done) => {
  if (!done) return
  stopTimer()
  sseClose()
  await store.refreshAssets(props.workId)
  await store.loadOverview(props.workId)
  ElMessage.success('合成完成')
})

function stopTimer() {
  if (timer) {
    window.clearInterval(timer)
    timer = undefined
  }
}

function closeSse() {
  sseClose()
  stopTimer()
  taskId.value = ''
}

// ---------------------------------------------------------------- 重合成
/** 重合成范围：受影响片段 / 整章 / 全本 */
const resynthScope = ref<'affected' | 'chapter' | 'full'>('affected')
const resynthScopes = [
  { value: 'affected', label: '仅重算受影响片段' },
  { value: 'chapter', label: '整章重合成' },
  { value: 'full', label: '全本重合成' },
] as const

/** 提交重合成：范围只影响提示语，实际都走 range/full（后端按受影响集扩范围） */
function submitResynth() {
  startSynth(resynthScope.value === 'affected' ? 'range' : resynthScope.value === 'chapter' ? 'range' : 'full')
}

/** 重合成耗时估算：每段约 6.5 秒（与后端 POC StubTTS 的量级一致） */
const resynthEstimate = computed(() => Math.max(5, Math.round(editedSegmentIds.value.size * 6.5)))

/** 被人工改过的片段 id 集合（重合成范围提示用） */
const editedSegmentIds = computed(() => new Set(
  store.edits.filter((e) => e.object_type === 'segment' && e.object_id).map((e) => e.object_id as number),
))

// ---------------------------------------------------------------- 播放器
/** 主推资产：优先样章，其次全本，兜底第一条 */
const featuredAsset = computed<AudioAsset | null>(() => {
  const list = store.assets
  return list.find((a) => a.kind === 'sample') ?? list.find((a) => a.kind === 'full') ?? list[0] ?? null
})

/** 双轨波形：旁白轨与角色轨用不同 seed，视觉上能区分 */
const laneNarr = computed(() => mkBars(74, 1.0))
const laneVoice = computed(() => mkBars(74, 1.7))

function assetName(a: AudioAsset): string {
  if (a.chapter_id) {
    const c = store.chapters.find((x) => x.id === a.chapter_id)
    if (c) return c.title
  }
  return { sample: '样章', chapter: '分章音频', role_track: '角色轨', full: '全本' }[a.kind] ?? '音频'
}

function kindText(kind: string): string {
  return { sample: '样章', chapter: '分章', role_track: '角色轨', full: '全本' }[kind] ?? kind
}

/** 播放音频资产 */
function playAsset(a: AudioAsset | null) {
  if (!a) {
    ElMessage.warning('还没有可播放的音频')
    return
  }
  playUrl(a.url)
}

/** 统一播放入口：浏览器可能拦截自动播放，失败给提示 */
function playUrl(url: string) {
  new Audio(url).play().catch(() => ElMessage.warning('浏览器阻止了自动播放，请手动点击'))
}

function download(a: AudioAsset | null) {
  if (!a) return
  openUrl(a.url)
}

/** 新窗口打开链接（模板里拿不到 window，统一走这个方法） */
function openUrl(url: string) {
  window.open(url, '_blank')
}

/** 复制分享链接到剪贴板（补上 origin，避免相对路径不可用） */
async function copyLink(a: AudioAsset | null) {
  if (!a) return
  const url = `${location.origin}${a.url}`
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('分享链接已复制')
  } catch {
    ElMessage.info(url)
  }
}

onUnmounted(stopTimer)
</script>
