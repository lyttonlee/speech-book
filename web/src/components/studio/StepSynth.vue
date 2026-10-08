<template>
  <div class="grid" style="grid-template-columns: 1.4fr 1fr">
    <!-- ============ 左：合成范围 / 样章试听 / 章节进度 ============ -->
    <div class="col gap-4">
      <div class="panel">
        <div class="card-h"><h3>合成范围</h3></div>
        <div class="row gap-3 wrap">
          <div class="segmented">
            <button :class="{ active: scope === 'sample' }" @click="scope = 'sample'">
              样章先行（前 2 章）
            </button>
            <button :class="{ active: scope === 'full' }" @click="scope = 'full'">
              全本合成（{{ chapterCount }} 章）
            </button>
          </div>
          <span class="badge acc"><span class="dot"></span>预计 {{ estimate }} 分钟</span>
        </div>

        <div class="row gap-3 mt wrap">
          <button class="btn btn-primary btn-lg" :loading="synthing" @click="startSynth">
            ▶ 开始合成
          </button>
          <button class="btn btn-ghost" @click="retry" :disabled="!lastFailed">重试上次任务</button>
        </div>

        <hr class="divider" />

        <div class="field" style="margin-bottom: 0">
          <label class="label">实时进度（SSE）</label>
          <div class="progress"><i :style="{ width: progress + '%' }"></i></div>
          <div class="row between mt-2">
            <span class="sm">{{ stageText }}</span>
            <span class="mono tiny muted">{{ progress }}%</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="card-h">
          <h3>样章试听</h3>
          <span :class="['badge', audioUrl ? 'ok' : '']"><span class="dot"></span>{{ audioUrl ? '合成完成' : '待合成' }}</span>
        </div>
        <div class="player mt-2">
          <button class="play" @click="togglePlay">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
          </button>
          <div class="wave">
            <i v-for="(h, i) in wave" :key="i" :style="{ height: h + '%' }"></i>
          </div>
          <div class="time">{{ timeText }}</div>
        </div>
        <audio ref="audioEl" :src="audioUrl" controls style="width: 100%; margin-top: 10px"></audio>
        <div class="row gap-2 mt">
          <button class="btn btn-sm" @click="download">下载</button>
          <button class="btn btn-sm" @click="copyLink">分享</button>
          <span class="tiny muted right">{{ metaText }}</span>
        </div>
      </div>

      <div class="panel">
        <div class="card-h">
          <h3>章节进度</h3>
          <span class="sub">全本 {{ chapterCount }} 章 · 已完成 {{ finishedChapters }} 章</span>
        </div>
        <div v-for="c in chapterRows" :key="c.id" class="chapter-item">
          <span class="cno">Ch.{{ c.order }}</span>
          <span class="sm" style="width: 72px">{{ c.title }}</span>
          <div class="bar progress thin"><i :style="{ width: c.progress + '%' }"></i></div>
          <span :class="['badge', c.cls]"><span class="dot"></span>{{ c.text }}</span>
          <button class="icon-btn" :disabled="!c.canPlay" @click="playChapter(c)">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
          </button>
        </div>
        <p v-if="!chapterRows.length" class="hint">还没有章节数据，先回上一步做解析。</p>
      </div>
    </div>

    <!-- ============ 右：任务记录 / 分段试听 ============ -->
    <div class="col gap-4">
      <div class="panel">
        <div class="card-h"><h3>任务记录</h3></div>
        <table class="table">
          <thead><tr><th>任务</th><th>状态</th><th>耗时</th></tr></thead>
          <tbody>
            <tr v-for="t in taskRows" :key="t.name">
              <td>{{ t.name }}</td>
              <td><span :class="['badge', t.cls]"><span class="dot"></span>{{ t.text }}</span></td>
              <td class="mono">{{ t.time }}</td>
            </tr>
            <tr v-if="!taskRows.length"><td colspan="3" class="hint">暂无任务</td></tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <div class="card-h"><h3>分段试听</h3><span class="sub">点击定位</span></div>
        <div class="col gap-2">
          <div
            v-for="s in previewSegments" :key="s.id"
            class="card row between" style="padding: 10px 14px; cursor: pointer"
            @click="playPreview(s)"
          >
            <span class="sm">{{ pad(s.order) }} · {{ trim(s.text) }}</span>
            <span :class="['badge', s.type === 'dialogue' ? 'acc' : '']">
              {{ s.speaker_name || '旁白' }}
            </span>
          </div>
          <p v-if="!previewSegments.length" class="hint">解析完成后这里列出可跳播的片段。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import { useTaskSSE } from '@/composables/useSSE'
import * as synthApi from '@/api/synth'
import type { AudioAsset, Segment } from '@/types'

/**
 * 步骤四「合成试听」（design/studio.html §步骤 4）。
 *
 * 进度全部由 SSE 推送（useTaskSSE），完成后拉一次合成状态拿音频地址，
 * 章节进度按「后端资产 → 章节」聚合，而不是再发一轮请求。
 */

const props = defineProps<{ workId: number }>()

const store = useWorkStore()

// ---------------------------------------------------------------- 合成任务
/** 合成范围：sample=样章（前 2 章）/ full=全本 */
const scope = ref<'sample' | 'full'>('sample')
const synthing = ref(false)
/** 上一次失败的任务，用于「重试上次任务」 */
const lastFailed = ref(false)
const audioUrl = ref('')
const metaText = ref('等待合成')

const synthTaskId = ref('')
const { progress, stage, done, failed, errorMsg, connect, close } = useTaskSSE(synthTaskId)

/** 阶段文案：跑的时候显示 SSE 推来的阶段，跑完了显示当前状态 */
const stageText = computed(() => {
  if (failed.value) return errorMsg.value || '任务失败'
  if (done.value) return '合成完成，可下载或继续全本合成'
  return stage.value || '排队中…'
})

const estimate = computed(() => Math.max(1, Math.round(store.chapters.length * 2.2)))

// ---------------------------------------------------------------- 样章播放器
const audioEl = ref<HTMLAudioElement | null>(null)
/** 波形高度：确定性正弦，重渲染不乱跳 */
const wave = computed(() => Array.from({ length: 60 }, (_, i) => 16 + Math.abs(Math.sin(i * 0.38)) * 74))
const timeText = ref('00:00 / 00:00')

/** 播放 / 暂停切换；没音频时先提示用户跑一次合成 */
function togglePlay() {
  if (!audioEl.value) return ElMessage.info('还没有合成产物，先点「开始合成」')
  audioEl.value.paused ? audioEl.value.play() : audioEl.value.pause()
}

/** 下载：直接跳静态文件地址（不走 /api/v1 前缀） */
function download() {
  if (!audioUrl.value) return ElMessage.info('暂无可下载的文件')
  window.open(audioUrl.value, '_blank')
}

/** 分享：把音频地址写进剪贴板 */
async function copyLink() {
  if (!audioUrl.value) return ElMessage.info('暂无可分享的链接')
  try {
    await navigator.clipboard.writeText(audioUrl.value)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.warning('浏览器拒绝了剪贴板权限')
  }
}

// ---------------------------------------------------------------- 章节进度
interface ChapterRow {
  id: number
  order: number
  title: string
  progress: number
  cls: string
  text: string
  canPlay: boolean
  url: string
}

/** 章节 → 进度：有合成资产按资产时长占比，没有则看解析状态 */
const chapterRows = computed<ChapterRow[]>(() => {
  const byChapter = new Map<number, AudioAsset[]>()
  for (const a of store.assets) {
    if (!a.chapter_id) continue
    byChapter.set(a.chapter_id, [...(byChapter.get(a.chapter_id) ?? []), a])
  }
  return store.chapters.map((c) => {
    const list = byChapter.get(c.id) ?? []
    const ready = list.filter((a) => a.status === 'ready')
    const asset = ready[0]
    const ratio = c.segment_count ? ready.length / Math.max(1, c.segment_count) * 100 : 0
    if (asset) {
      return {
        id: c.id, order: c.order, title: c.title,
        progress: Math.min(100, Math.round(ratio || 100)),
        cls: 'ok', text: '完成', canPlay: true, url: asset.url,
      }
    }
    return {
      id: c.id, order: c.order, title: c.title,
      progress: c.status === 'done' ? 0 : 0,
      cls: '', text: c.status === 'done' ? '待合成' : '未解析',
      canPlay: false, url: '',
    }
  })
})

const chapterCount = computed(() => store.chapters.length)
const finishedChapters = computed(() => chapterRows.value.filter((c) => c.text === '完成').length)

/** 点章节的 ▶：直接放该章第一条产物 */
function playChapter(c: ChapterRow) {
  if (!c.url) return
  window.open(c.url, '_blank')
}

// ---------------------------------------------------------------- 分段试听
const previewSegments = computed<Segment[]>(() => store.segments.slice(0, 6))
function pad(n: number) {
  return String(n).padStart(2, '0')
}
function trim(v: string) {
  return v.length > 18 ? `${v.slice(0, 18)}…` : v
}
/** 跳播某个片段：弹出该说话人绑定音色的试听（暂无片段级音频，用播放器兜底） */
function playPreview(s: Segment) {
  const role = store.roles.find((r) => r.name === s.speaker_name)
  ElMessage.info(role ? `试听「${role.name}」音色：${s.text.slice(0, 14)}…` : '该片段尚未识别说话人')
}

/** 任务记录：优先展示后端流水线已完成的段，再补一条合成 */
const taskRows = computed(() => store.pipeline
  .filter((p) => p.status === 'done' || p.status === 'error')
  .map((p) => ({
    name: p.label,
    cls: p.status === 'done' ? 'ok' : 'warn',
    text: p.status === 'done' ? '成功' : '失败',
    time: p.seconds ? `${p.seconds}s` : '—',
  })))

// ---------------------------------------------------------------- 动作
/**
 * 起合成任务。
 * 保存绑定与 scope 都在这一步生效，所以直接调后端；进度交给 SSE。
 */
async function startSynth() {
  synthing.value = true
  audioUrl.value = ''
  timeText.value = '00:00 / 00:00'
  try {
    const r = await synthApi.startSynth(props.workId, scope.value)
    synthTaskId.value = r.task_id
    progress.value = 0
    connect()
  } catch (err) {
    synthing.value = false
    lastFailed.value = true
    ElMessage.error(err instanceof Error ? err.message : '合成任务启动失败')
  }
}

/** 重试：背同 scope 再跑一次（POC 不保留上次任务上下文，按当前范围重跑） */
function retry() {
  scope.value = scope.value === 'sample' ? 'full' : 'sample'
  startSynth()
}

// 任务跑完 → 拉一次合成状态拿到音频地址，并刷新资产列表
watch(done, async (v) => {
  if (!v || !synthTaskId.value) return
  synthing.value = false
  close()
  try {
    const st = await synthApi.synthStatus(props.workId, synthTaskId.value)
    audioUrl.value = st.audio_url || ''
    if (st.duration) {
      const s = Math.round(st.duration)
      timeText.value = `00:00 / ${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
    }
    metaText.value = st.audio_url ? '128 kbps · 44.1kHz · 已就绪' : '暂无产物'
    await store.refreshAssets(props.workId)
  } catch {
    metaText.value = '产物信息获取失败'
  }
})

watch(failed, (v) => {
  if (!v) return
  synthing.value = false
  lastFailed.value = true
})

onMounted(async () => {
  // 入口可能直接落在步骤四（比如从工作空间返回），先补齐章节 / 段落 / 资产
  if (!store.chapters.length) await store.loadOverview(props.workId).catch(() => {})
})

defineExpose({ startSynth })
</script>
