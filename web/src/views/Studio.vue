<template>
  <div class="studio">
    <header class="topbar">
      <div class="brand">有声书智能制作平台 · POC</div>
      <el-button text @click="onLogout">退出</el-button>
    </header>

    <main class="content">
      <!-- 步骤一：上传文本 + 解析 -->
      <el-card class="panel" shadow="never">
        <template #header><b>1. 上传文本并解析</b></template>
        <el-input v-model="workName" placeholder="作品名称，如《我的小说》" class="mb" />
        <el-input v-model="novelText" type="textarea" :rows="8"
                  placeholder="粘贴小说文本（支持「第一章」分章、引号对话、说话人「张三说：…」）" class="mb" />
        <el-button type="primary" :loading="parsing" @click="onParse">新建并解析</el-button>

        <div v-if="parseSSE.progress.value > 0 || parseSSE.done.value" class="mt">
          <el-progress :percentage="parseSSE.progress.value" :status="parseSSE.done.value ? 'success' : ''" />
          <div class="hint">{{ parseSSE.stage.value }}</div>
        </div>
      </el-card>

      <!-- 解析结果 -->
      <el-card v-if="segments.length" class="panel" shadow="never">
        <template #header>
          <b>2. 解析结果</b>
          <span class="muted"> 角色 {{ roles.length }} · 片段 {{ segments.length }}</span>
        </template>
        <div class="roles mb">
          <el-tag v-for="r in roles" :key="r.id" class="role-tag" :type="r.level === 'main' ? 'danger' : 'info'">
            {{ r.name }}（{{ r.level }}·{{ r.line_count }}句）
          </el-tag>
        </div>
        <el-table :data="segments" max-height="360" size="small">
          <el-table-column prop="type" label="类型" width="90">
            <template #default="{ row }">{{ typeLabel[row.type] }}</template>
          </el-table-column>
          <el-table-column prop="text" label="文本" show-overflow-tooltip />
          <el-table-column prop="speaker_name" label="说话人" width="110" />
          <el-table-column prop="emotion" label="情绪" width="90" />
          <el-table-column label="置信度" width="110">
            <template #default="{ row }">
              <span :class="{ low: row.low_conf }">{{ row.confidence.toFixed(2) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 步骤三：角色绑定 / 音色选择 -->
      <el-card v-if="bindRows.length" class="panel" shadow="never">
        <template #header><b>3. 角色绑定 / 音色选择</b></template>
        <div class="hint mb">
          为每个角色与旁白选择音色，保存后合成将按此映射生成多角色音频（旁白 = 角色 id 0）。
        </div>
        <div class="bind-actions mb">
          <el-button @click="onAutoBind">自动绑定</el-button>
          <el-button type="primary" @click="onSaveBindings">保存绑定</el-button>
        </div>
        <el-table :data="bindRows" size="small" max-height="320">
          <el-table-column label="角色 / 旁白" width="170">
            <template #default="{ row }">
              <el-tag :type="row.isNarrator ? 'info' : 'danger'" size="small" effect="light">
                {{ row.isNarrator ? '旁白' : '角色' }} · {{ row.name }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="lineCount" label="台词数" width="90" />
          <el-table-column label="音色" min-width="220">
            <template #default="{ row }">
              <el-select v-model="row.voiceId" placeholder="选择音色" size="small" style="width: 100%">
                <el-option
                  v-for="v in (row.isNarrator ? narratorOptions : roleOptions)"
                  :key="v.id"
                  :label="v.name + (v.tags && v.tags.length ? '（' + v.tags.join('/') + '）' : '')"
                  :value="v.id"
                />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 步骤四：样章合成 -->
      <el-card v-if="bindRows.length" class="panel" shadow="never">
        <template #header><b>4. 样章合成（前 1-2 章）</b></template>
        <el-button type="success" :loading="synthing" @click="onSynth('sample')">样章先行</el-button>
        <el-button :loading="synthing" @click="onSynth('full')">全本合成</el-button>

        <div v-if="synthSSE.progress.value > 0 || synthSSE.done.value" class="mt">
          <el-progress :percentage="synthSSE.progress.value" :status="synthSSE.done.value ? 'success' : (synthSSE.failed.value ? 'exception' : '')" />
          <div class="hint">{{ synthSSE.stage.value }}</div>
        </div>

        <div v-if="audioUrl" class="mt audio">
          <audio :src="audioUrl" controls />
          <div class="hint">合成音频（POC 为可听 tone 占位，生产接入 IndexTTS/Qwen3-TTS；不同音色对应不同基频）</div>
        </div>
      </el-card>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useWorkStore } from '@/stores/work'
import { useTaskSSE } from '@/composables/useSSE'
import * as worksApi from '@/api/works'
import * as parseApi from '@/api/parse'
import * as synthApi from '@/api/synth'
import * as voicesApi from '@/api/voices'
import * as bindingsApi from '@/api/bindings'
import type { Role, Segment, Voice, Binding } from '@/types'

const router = useRouter()
const user = useUserStore()
const work = useWorkStore()

const workName = ref('')
const novelText = ref('张三说：“你好啊，好久不见。”\n李四回答：“你也好，最近可好？”\n她心中一阵难过……\n“我们走吧。”他说道。')
const roles = ref<Role[]>([])
const segments = ref<Segment[]>([])
const audioUrl = ref('')
const parsing = ref(false)
const synthing = ref(false)

// 角色绑定 / 音色选择状态
interface BindRow {
  roleId: number
  name: string
  lineCount: number
  isNarrator: boolean
  voiceId: number | null
}
const bindRows = ref<BindRow[]>([])

const narratorOptions = computed(() =>
  work.voices.filter((v: Voice) => (v.tags || []).includes('旁白')),
)
const roleOptions = computed(() =>
  work.voices.filter((v: Voice) => !(v.tags || []).includes('旁白')),
)
const narratorLineCount = computed(
  () => segments.value.filter((s) => s.type === 'narration' || s.type === 'psychology').length,
)

const FEMALE_HINT = ['她', '姐', '妹', '女', '娘', '妻', '姑', '姨', '母', '女儿', '公主', '女王']
function firstVoiceWithTag(tag: string): number | null {
  return work.voices.find((v: Voice) => (v.tags || []).includes(tag))?.id ?? null
}
function defaultNarratorVoiceId(): number | null {
  return firstVoiceWithTag('旁白')
}
function defaultRoleVoiceId(name: string): number | null {
  if (FEMALE_HINT.some((c) => name.includes(c))) {
    const fv = firstVoiceWithTag('女声')
    if (fv) return fv
  }
  return roleOptions.value[0]?.id ?? null
}
function buildRows(): BindRow[] {
  const rows: BindRow[] = [
    {
      roleId: 0,
      name: '旁白',
      lineCount: narratorLineCount.value,
      isNarrator: true,
      voiceId: defaultNarratorVoiceId(),
    },
  ]
  for (const r of work.roles) {
    rows.push({
      roleId: r.id,
      name: r.name,
      lineCount: r.line_count,
      isNarrator: false,
      voiceId: defaultRoleVoiceId(r.name),
    })
  }
  return rows
}

async function loadBindingStep() {
  if (!work.currentWork) return
  const [vs, bnd] = await Promise.all([
    voicesApi.listVoices(),
    bindingsApi.listBindings(work.currentWork.id),
  ])
  work.setVoices(vs.items)
  const map = new Map<number, number | null>(
    (bnd.items as Binding[]).map((b) => [b.role_id, b.voice_id]),
  )
  const rows = buildRows()
  for (const r of rows) {
    if (map.has(r.roleId)) r.voiceId = map.get(r.roleId) ?? null
  }
  bindRows.value = rows
}

async function onAutoBind() {
  if (!work.currentWork) return
  await bindingsApi.autoBind(work.currentWork.id)
  const bnd = await bindingsApi.listBindings(work.currentWork.id)
  const map = new Map<number, number | null>(
    (bnd.items as Binding[]).map((b) => [b.role_id, b.voice_id]),
  )
  for (const r of bindRows.value) {
    if (map.has(r.roleId)) r.voiceId = map.get(r.roleId) ?? null
  }
  ElMessage.success('已按音色标签自动绑定')
}

async function onSaveBindings() {
  if (!work.currentWork) return
  const items: Binding[] = bindRows.value.map((r) => ({
    role_id: r.roleId,
    voice_id: r.voiceId,
    params: {},
  }))
  await bindingsApi.setBindings(work.currentWork.id, items)
  ElMessage.success('绑定已保存')
}

const parseTaskId = ref('')
const parseSSE = useTaskSSE(parseTaskId)
const synthTaskId = ref('')
const synthSSE = useTaskSSE(synthTaskId)

const typeLabel: Record<string, string> = {
  narration: '旁白',
  dialogue: '对话',
  psychology: '心理',
}

watch(parseSSE.done, async (v) => {
  if (v && work.currentWork) {
    const [seg, role] = await Promise.all([
      parseApi.getSegments(work.currentWork.id),
      parseApi.getRoles(work.currentWork.id),
    ])
    segments.value = seg.items
    roles.value = role.items
    work.setSegments(seg.items)
    work.setRoles(role.items)
    parsing.value = false
    await loadBindingStep()
  }
})

watch(synthSSE.done, async (v) => {
  if (v && work.currentWork && synthTaskId.value) {
    const st = await synthApi.synthStatus(work.currentWork.id, synthTaskId.value)
    audioUrl.value = st.audio_url || ''
    synthing.value = false
  }
})

async function onParse() {
  if (!workName.value.trim()) return ElMessage.warning('请填写作品名称')
  if (!novelText.value.trim()) return ElMessage.warning('请粘贴小说文本')
  parsing.value = true
  audioUrl.value = ''
  segments.value = []
  try {
    const w = await worksApi.createWork({ name: workName.value.trim() })
    work.setWork(w)
    await worksApi.mergeText(w.id, 'novel.txt', novelText.value)
    const r = await parseApi.startParse(w.id)
    parseTaskId.value = r.task_id
    parseSSE.progress.value = 0
    parseSSE.done.value = false
    parseSSE.connect()
  } catch {
    parsing.value = false
  }
}

async function onSynth(scope: 'sample' | 'full') {
  if (!work.currentWork) return
  synthing.value = true
  audioUrl.value = ''
  try {
    // 合成前先保存当前角色-音色绑定，确保 bind→synth 全链路生效
    const items: Binding[] = bindRows.value.map((r) => ({
      role_id: r.roleId,
      voice_id: r.voiceId,
      params: {},
    }))
    await bindingsApi.setBindings(work.currentWork.id, items)
    const r = await synthApi.startSynth(work.currentWork.id, scope)
    synthTaskId.value = r.task_id
    synthSSE.progress.value = 0
    synthSSE.done.value = false
    synthSSE.failed.value = false
    synthSSE.connect()
  } catch {
    synthing.value = false
  }
}

function onLogout() {
  user.logout()
  router.push('/login')
}
</script>

<style scoped>
.studio { min-height: 100vh; }
.topbar { display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px; background: #fff; border-bottom: 1px solid #ebeef5; }
.brand { font-weight: 600; }
.content { max-width: 960px; margin: 20px auto; padding: 0 16px; display: flex; flex-direction: column; gap: 16px; }
.panel { border-radius: 10px; }
.mb { margin-bottom: 12px; }
.mt { margin-top: 12px; }
.hint { color: #909399; font-size: 12px; margin-top: 4px; }
.muted { color: #909399; font-weight: 400; font-size: 13px; margin-left: 8px; }
.role-tag { margin-right: 6px; margin-bottom: 6px; }
.low { color: #e6a23c; font-weight: 600; }
.audio audio { width: 100%; margin-top: 8px; }
</style>
