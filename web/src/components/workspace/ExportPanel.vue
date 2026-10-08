<template>
  <!-- ==================== 10. 导出成品 ==================== -->
  <section class="section anchor" id="export">
    <div class="sec-head">
      <div>
        <h2>导出成品</h2>
        <div class="desc">
          全部合成完成即可导出；当前预计产物 {{ store.assets.length }} 个文件。
        </div>
      </div>
    </div>

    <div class="grid" style="grid-template-columns:1fr 1fr;align-items:start">
      <div class="panel">
        <div class="card-h"><h3>导出配置</h3><span class="sub">会记住为默认</span></div>
        <div class="grid cols-2 gap-4">
          <div class="field"><label class="label">音频格式</label>
            <select v-model="form.format" class="select">
              <option value="mp3">MP3 128 kbps</option><option value="mp3_192">MP3 192 kbps</option>
              <option value="wav">WAV 44.1kHz</option><option value="m4b">M4B（有声书）</option>
            </select>
          </div>
          <div class="field"><label class="label">分片方式</label>
            <select v-model="form.split" class="select">
              <option value="single">整本单文件</option><option value="chapter">按章节</option>
              <option value="20min">每 20 分钟</option>
            </select>
          </div>
          <div class="field"><label class="label">字幕</label>
            <select v-model="form.subtitle" class="select">
              <option value="both">SRT + LRC</option><option value="srt">仅 SRT</option><option value="none">不导出</option>
            </select>
          </div>
          <div class="field"><label class="label">片头片尾</label>
            <select v-model="form.head_tail" class="select">
              <option value="none">无</option><option value="both">片头 3s + 片尾 2s</option><option value="tail">仅片尾</option>
            </select>
          </div>
        </div>
        <div class="col gap-3 mt">
          <div class="row between">
            <span class="sm dim">背景音乐（低音量垫底）</span>
            <button :class="['switch', { on: form.bgm }]" @click="form.bgm = !form.bgm"></button>
          </div>
          <div class="row between">
            <span class="sm dim">输出时做响度归一（LUFS -16）</span>
            <button :class="['switch', { on: form.loudnorm }]" @click="form.loudnorm = !form.loudnorm"></button>
          </div>
          <div class="row between">
            <span class="sm dim">导出后写入隐式水印（仅自身内容）</span>
            <button :class="['switch', { on: form.watermark }]" @click="form.watermark = !form.watermark"></button>
          </div>
        </div>
        <hr class="divider" />
        <div class="row between">
          <span class="tiny muted">{{ store.assets.length }} 个音频 · 字幕 {{ form.subtitle === 'none' ? '不导出' : '随音频' }}</span>
          <el-button class="btn btn-primary" :loading="exporting" @click="doExport">生成导出任务</el-button>
        </div>
      </div>

      <div class="panel">
        <div class="card-h"><h3>导出记录</h3><span class="sub">历史 {{ exports.length }} 次</span></div>
        <table class="table">
          <thead><tr><th>时间</th><th>格式</th><th>时长</th><th>状态</th><th class="right"></th></tr></thead>
          <tbody>
            <tr v-for="r in exports" :key="r.id">
              <td class="mono">{{ fmtTime(r.created_at) }}</td>
              <td>{{ r.format }}</td>
              <td class="mono">{{ fmtDuration(r.duration) }}</td>
              <td><span class="badge ok"><span class="dot"></span>可下载</span></td>
              <td class="right">
                <el-button class="btn btn-sm" @click="openUrl(r.url)">下载</el-button>
              </td>
            </tr>
            <tr v-if="!exports.length">
              <td colspan="5" class="tiny muted">还没有导出记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * 导出成品区块（design/workspace.html §10）。
 *
 * 左侧是导出配置表单（格式/分片/字幕/片头片尾/BGM/响度归一/水印），右侧是历史导出记录。
 * POC 阶段后端不真跑 ffmpeg，只把配置落库并返回一个可下载的产物地址，
 * 所以这里不必管转码进度，拿到 url 即可展示「下载」。
 */

import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import * as exportApi from '@/api/export'
import { fmtTime } from '@/utils/format'
import { fmtDuration } from '@/utils/status'

const props = defineProps<{ workId: number }>()

const store = useWorkStore()

/** 导出中的按钮 loading */
const exporting = ref(false)
/** 导出历史（新建任务成功后会 push 一条） */
const exports = ref<any[]>([])
/** 最近一次导出产物的下载地址，供「下载」按钮使用 */
const lastUrl = ref('')

/** 导出配置表单：字段与 docs/接口文档.md §14 startExport 的 params 一一对应 */
interface ExportForm {
  format: string
  split: string
  subtitle: string
  head_tail: string
  bgm: boolean
  loudnorm: boolean
  watermark: boolean
}
const form = reactive<ExportForm>({
  format: 'mp3',
  split: 'chapter',
  subtitle: 'both',
  head_tail: 'none',
  bgm: false,
  loudnorm: true,
  watermark: false,
})

/** 拉取导出历史。失败不打扰——导出区块是纯展示，列表空了用户看得见。 */
async function loadExports() {
  try {
    const res = await exportApi.listExports(props.workId)
    exports.value = res.items ?? []
  } catch {
    exports.value = []
  }
}

/** 提交导出任务：成功后把新记录插到表头，并顺手刷新音频列表（导出的产物会出现在配音区） */
async function doExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const res = await exportApi.startExport(props.workId, { ...form })
    lastUrl.value = res.url ?? ''
    // 后端返回 { record_id, url, expires_at }，这里补全成表格行，避免再发一次列表请求
    exports.value.unshift({
      id: res.record_id,
      format: form.format,
      duration: 0,
      created_at: new Date().toISOString(),
      url: res.url,
    })
    store.refreshAssets(props.workId)
    await loadExports()
    ElMessage.success('导出任务已创建')
  } catch (err: any) {
    // 后端会抛业务错误（例如还有章节未合成完），直接把 message 透出
    ElMessage.error(err?.message ?? '导出任务创建失败')
  } finally {
    exporting.value = false
  }
}

/** 新窗口打开下载地址。用 method 包一层，模板里访问不到 window。 */
function openUrl(url: string) {
  if (!url) return
  window.open(url, '_blank')
}

onMounted(loadExports)

defineExpose({ doExport, loadExports })
</script>
