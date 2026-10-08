<template>
  <section class="grid" style="grid-template-columns: 1.5fr 1fr">
    <!-- ============ 左：小说原文（主录入区） ============ -->
    <div class="panel">
      <div class="card-h">
        <h3>小说原文</h3><span class="sub">支持 .txt 导入或直接粘贴</span>
      </div>

      <div class="field">
        <label class="label">作品名称</label>
        <input v-model="workName" class="input" placeholder="例如《星河彼端》" />
      </div>

      <div class="field">
        <label class="label">正文</label>
        <textarea
          v-model="text"
          class="textarea"
          style="min-height: 280px"
          placeholder="第一章 启航&#10;&#10;夜色像一块浸了水的绒布，沉沉压在港口上。张三低声说道：“今天必须出发。”"
        ></textarea>
      </div>

      <div class="row between wrap">
        <span class="tiny muted">
          已录入 <b style="color: var(--accent)">{{ charCount }}</b> 字 · 预计
          <b>{{ estChapters }}</b> 章节 · 约 <b>{{ estMinutes }}</b> 分钟音频
        </span>
        <button class="btn btn-primary btn-lg" :loading="parsing" @click="startParse">
          {{ parsing ? '解析中…' : '开始解析 →' }}
        </button>
      </div>

      <!-- 解析失败的兜底提示：POC 里任务可能直接失败，给用户明确出口 -->
      <p v-if="parseError" class="hint" style="color: var(--danger)">{{ parseError }}</p>
    </div>

    <!-- ============ 右：导入文件 + 解析设置 ============ -->
    <div class="col gap-4">
      <div class="panel">
        <div class="card-h"><h3>导入文件</h3></div>
        <div
          class="dropzone"
          :class="{ over: dragging }"
          @click="pickFile"
          @dragover.prevent="dragging = true"
          @dragleave="dragging = false"
          @drop.prevent="onDrop"
        >
          <div class="ic" style="background: var(--accent-soft); color: var(--accent)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
            </svg>
          </div>
          <b style="color: var(--text-1)">拖拽 .txt 到此处</b>
          <p class="tiny mt-2">
            或点击选择文件 · 单文件 ≤ 5MB
          </p>
        </div>
      </div>

      <div class="panel">
        <div class="card-h"><h3>解析设置</h3></div>
        <div class="field">
          <label class="label">章节切分</label>
          <select v-model="splitMode" class="select">
            <option value="auto">自动识别「第X章」（推荐）</option>
            <option value="blank">按空行分段</option>
            <option value="regex">自定义正则</option>
          </select>
        </div>
        <div class="field">
          <label class="label">情绪识别</label>
          <select v-model="emotionMode" class="select">
            <option value="heuristic">标点启发式（POC 默认）</option>
            <option value="llm" disabled>LLM 增强（生产）</option>
          </select>
        </div>
        <p class="hint">
          切分与情绪档位当前为前端配置项；后端解析服务在 POC 阶段固定用默认规则，
          接入 LLM 适配器后即可按此透传。
        </p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import { useTaskSSE } from '@/composables/useSSE'
import * as worksApi from '@/api/works'
import * as parseApi from '@/api/parse'
import type { Work } from '@/types'

/**
 * 步骤一「上传文本」（design/studio.html §步骤 1）。
 *
 * 职责边界：只负责把文本交给后端并跟踪解析任务，
 * 解析产物的展示交给 StepParse，避免本文件膨胀。
 */

const emit = defineEmits<{ parsed: [work: Work] }>()

const store = useWorkStore()

// ---------------------------------------------------------------- 表单状态
const workName = ref('')
/** 正文默认给一段样例，方便 POC 直接点「开始解析」看全链路 */
const text = ref(
  '第一章 启航\n\n'
  + '夜色像一块浸了水的绒布，沉沉压在港口上。张三低声说道：“今天必须出发。”\n'
  + '李四回答：“风浪太大了，再等等吧。”\n'
  + '张三望着远处灯塔明明灭灭的光，心中一阵难过——他知道，等下去就再没有机会了。\n'
  + '“我们走吧。”他说道。',
)

/** 切分方式 / 情绪档位：当前仅影响界面与未来透传，不进后端 */
const splitMode = ref('auto')
const emotionMode = ref('heuristic')

const parsing = ref(false)
const parseError = ref('')
const dragging = ref(false)

// ---------------------------------------------------------------- 派生统计
/** 正文字数（去空白，和编辑器里的计数口径保持一致） */
const charCount = computed(() => text.value.replace(/\s/g, '').length)

/**
 * 章节数预估：按「第X章」标题行数估。
 * 解析前没有真数据，这里只做展示级估算，解析完成由 StepParse 用真实值覆盖。
 */
const estChapters = computed(() => {
  const hits = text.value.match(/第[0-9一二三四五六七八九十百]+章/g)
  return Math.max(1, hits?.length ?? text.value.split(/\n{2,}/).length)
})

/** 音频时长粗估：按中文播音 300 字/分钟 */
const estMinutes = computed(() => Math.max(1, Math.round(charCount.value / 300)))

// -------------------------------------------------------------- 文件导入
/** 点击拖拽区 → 唤起系统文件选择 */
function pickFile() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.txt,text/plain'
  input.onchange = () => {
    if (input.files?.[0]) readFile(input.files[0])
  }
  input.click()
}

/** 拖拽放下 → 直接读文件，不再二次弹窗 */
function onDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) readFile(file)
}

/**
 * 读取 .txt 文件内容。
 * 只取文本部分忽略二进制/超大文件，避免把整个 5MB 塞进 textarea 卡死输入框。
 */
function readFile(file: File) {
  if (file.size > 5 * 1024 * 1024) {
    return ElMessage.warning('单文件请控制在 5MB 以内')
  }
  if (!workName.value.trim()) {
    workName.value = file.name.replace(/\.txt$/i, '')
  }
  const reader = new FileReader()
  reader.onload = () => {
    text.value = String(reader.result ?? '')
    ElMessage.success(`已导入 ${file.name}`)
  }
  reader.readAsText(file, 'utf-8')
}

// ------------------------------------------------------- 解析（含 SSE 进度）
const parseTaskId = ref('')
const {
  progress, stage, done, failed, errorMsg, connect, close,
} = useTaskSSE(parseTaskId)

/**
 * 从零建作品 → 写入正文 → 起解析任务。
 * 返回建好的作品对象，交给父组件记住 workId，后续步骤都基于它。
 */
async function startParse() {
  if (!workName.value.trim()) return ElMessage.warning('请先填写作品名称')
  if (!text.value.trim()) return ElMessage.warning('请先粘贴或导入正文')
  parsing.value = true
  parseError.value = ''
  try {
    const w = await worksApi.createWork({ name: workName.value.trim() })
    await worksApi.mergeText(w.id, 'novel.txt', text.value)
    store.setWork(w)
    const r = await parseApi.startParse(w.id)
    parseTaskId.value = r.task_id
    progress.value = 0
    // taskId 变了要重新建 EventSource，进度才会开始推
    connect()
  } catch (err) {
    // 建作品 / 传文本这步就在同步阶段失败，直接提示，不走 SSE
    parsing.value = false
    parseError.value = err instanceof Error ? err.message : '解析启动失败'
  }
}

// 解析任务结束（成功或失败）统一收尾：关掉 SSE、复位按钮
// 成功时父组件切到步骤二，由 StepParse 自己拉数据
watch(done, (v) => {
  parsing.value = false
  if (!v) return
  close()
  emit('parsed', store.currentWork!)
})

watch(failed, (v) => {
  parsing.value = false
  if (!v) return
  close()
  parseError.value = errorMsg.value || '解析任务失败，可点「重新解析」重试'
})

defineExpose({ startParse })
</script>
