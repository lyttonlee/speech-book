<template>
  <div class="grid" style="grid-template-columns: 1.6fr 1fr">
    <!-- ============ 左：角色 → 音色绑定 ============ -->
    <div class="panel">
      <div class="card-h">
        <h3>角色 → 音色绑定</h3>
        <span class="sub">旁白 role_id=0，角色按台词分配</span>
      </div>

      <div v-for="(r, i) in rows" :key="r.roleId" class="bind-row">
        <div class="avatar" :style="{ background: r.color }">{{ r.mark }}</div>
        <div class="who">
          <div>
            <b>{{ r.name }}</b>
            <div class="tiny muted">{{ r.desc }}</div>
          </div>
        </div>
        <div class="sel">
          <select v-model="r.voiceId" class="select">
            <option :value="null">— 未绑定（将使用默认音色） —</option>
            <option v-for="v in (r.isNarrator ? narratorVoices : roleVoices)" :key="v.id" :value="v.id">
              {{ v.name }}{{ (v.tags || []).length ? `（${v.tags.join('/')}）` : '' }}
            </option>
          </select>
        </div>
        <div class="acts">
          <button class="btn btn-ghost btn-sm" :disabled="r.voiceId == null" @click="preview(r)">
            ▶ 试听
          </button>
        </div>
      </div>
      <p v-if="!rows.length" class="hint">还没有解析出角色，先回上一步重新解析。</p>

      <div class="row gap-3 mt-6 wrap">
        <button class="btn" :loading="autoBinding" @click="autoBind">⚡ 自动绑定</button>
        <button class="btn btn-ghost" @click="resetAll">重置全部</button>
        <button class="btn btn-primary" :loading="saving" @click="saveBind">保存绑定，去合成 →</button>
        <a class="tiny muted right" href="javascript:;" @click="$router.push('/voices')">
          管理音色库 →
        </a>
      </div>
    </div>

    <!-- ============ 右：全局韵律 / 绑定预览 / 情绪映射 ============ -->
    <div class="col gap-4">
      <div class="panel">
        <div class="card-h">
          <h3>全局韵律微调</h3><span class="sub">作用于全部片段</span>
        </div>
        <div class="param-row">
          <span class="pname">整体语速</span>
          <input v-model.number="prosody.speed" type="range" class="slider" min="0.5" max="2" step="0.1" />
          <span class="pval">{{ prosody.speed.toFixed(1) }}×</span>
        </div>
        <div class="param-row">
          <span class="pname">整体音调</span>
          <input v-model.number="prosody.pitch" type="range" class="slider" min="-12" max="12" step="1" />
          <span class="pval">{{ prosody.pitch > 0 ? '+' : '' }}{{ prosody.pitch }}st</span>
        </div>
        <div class="param-row">
          <span class="pname">整体音量</span>
          <input v-model.number="prosody.gain" type="range" class="slider" min="-12" max="6" step="1" />
          <span class="pval">{{ prosody.gain > 0 ? '+' : '' }}{{ prosody.gain }}dB</span>
        </div>
        <div class="row between mt">
          <span class="sm dim">情绪映射自动覆盖整体参数</span>
          <button :class="['switch', { on: emotionOverride }]" @click="emotionOverride = !emotionOverride"></button>
        </div>
        <p class="hint">滑杆只影响预览与导出的合成参数；保存绑定后随绑定一起下发。</p>
      </div>

      <div class="panel">
        <div class="card-h"><h3>绑定预览</h3></div>
        <p class="tiny muted">按当前绑定播放开头（POC 为合成占位音）：</p>
        <div class="player mt-2">
          <button class="play" @click="preview(selectedRow || rows[0])">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
          </button>
          <div class="wave">
            <i v-for="(h, i) in wave" :key="i" :style="{ height: h + '%' }"></i>
          </div>
          <div class="time">{{ previewDuration }}</div>
        </div>
        <audio v-if="previewUrl" :src="previewUrl" controls style="width: 100%; margin-top: 10px"></audio>
        <ul class="tiny muted mt" style="padding-left: 18px; margin: 10px 0 0; line-height: 2">
          <li v-for="r in rows.slice(0, 3)" :key="r.roleId">
            {{ r.name }} → {{ voiceNameOf(r.voiceId) || '未绑定' }}
          </li>
        </ul>
      </div>

      <div class="panel">
        <div class="card-h"><h3>情绪 → 韵律映射</h3></div>
        <table class="table">
          <thead><tr><th>情绪</th><th>语速</th><th>音高</th></tr></thead>
          <tbody>
            <tr v-for="e in EMOTION_IR" :key="e.name">
              <td>{{ e.name }}</td><td class="mono">{{ e.speed }}</td><td class="mono">{{ e.pitch }}</td>
            </tr>
          </tbody>
        </table>
        <p class="hint">由 EmotionIR 驱动，生产环境可按引擎能力降级。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import * as voicesApi from '@/api/voices'
import * as bindingsApi from '@/api/bindings'
import * as rolesApi from '@/api/roles'
import type { Binding, Voice } from '@/types'

/**
 * 步骤三「角色绑定」（design/studio.html §步骤 3）。
 *
 * 一条 bind-row = 一个角色（含旁白 role_id=0）→ 一个音色的映射。
 * 保存时整体 PUT 覆盖，未绑定的角色留 null，由合成兜底取默认音色。
 */

const props = defineProps<{ workId: number }>()
const emit = defineEmits<{ next: [] }>()

const store = useWorkStore()
const router = useRouter()

// ---------------------------------------------------------------- 行模型
interface BindRow {
  roleId: number
  name: string
  desc: string
  mark: string
  color: string
  isNarrator: boolean
  voiceId: number | null
}

const PALETTE = ['#38bdf8', '#a78bfa', '#34d399', '#fbbf24', '#fb7185', '#22d3ee']

const rows = ref<BindRow[]>([])
const voices = ref<Voice[]>([])
const autoBinding = ref(false)
const saving = ref(false)

/** 全局韵律：纯前端参数，随绑定一起下发（后端存 Binding.params） */
const prosody = reactive({ speed: 1, pitch: 0, gain: 0 })
/** 是否允许情绪映射覆盖全局参数（关掉后全局值优先生效） */
const emotionOverride = ref(true)

const narratorVoices = computed(() => voices.value.filter((v) => (v.tags || []).includes('旁白')))
const roleVoices = computed(() => voices.value.filter((v) => !(v.tags || []).includes('旁白')))

/** 当前选中的行（绑定预览默认用它试听） */
const selectedRow = computed(() => rows.value.find((r) => r.voiceId != null) ?? rows.value[0] ?? null)

const EMOTION_IR = [
  { name: '急切', speed: '+15%', pitch: '+2st' },
  { name: '难过', speed: '-10%', pitch: '-1st' },
  { name: '担忧', speed: '-5%', pitch: '0' },
]

const previewUrl = ref('')
/** 预览音频时长文案（试听返回 duration 后覆盖） */
const previewDuration = ref('00:12')
/** 预览波形高度：用确定性正弦拼，避免每次渲染乱跳 */
const wave = computed(() => Array.from({ length: 46 }, (_, i) => 18 + Math.abs(Math.sin(i * 0.45)) * 70))

// ---------------------------------------------------------------- 加载
/**
 * 拉音色库 + 角色 + 绑定三份数据，合并成本地行模型。
 * 已有绑定优先（用户来回路过不该丢），没绑定就按标签猜一个默认值。
 */
async function load() {
  // 注意：解构顺序必须和 Promise.all 的入参顺序一一对应
  // （音色 → 绑定 → 角色），错位会导致 rs.items 变成 Binding[] 而编译报错
  const [vs, bnd, rs] = await Promise.all([
    voicesApi.listVoices(),
    bindingsApi.listBindings(props.workId),
    rolesApi.listRoles(props.workId),
  ])
  const voiceList = vs.items ?? []
  const roleList = rs.items ?? []
  voices.value = voiceList
  store.setVoices(voiceList)
  store.setRoles(roleList)
  // 绑定表是「角色 id → 音色 id」的一层映射，逐条塞进 Map 比一次性构造更好推断类型
  const map = new Map<number, number | null>()
  for (const b of bnd.items ?? []) map.set(b.role_id, b.voice_id)

  const next: BindRow[] = [{
    roleId: 0,
    name: '旁白',
    desc: `全部叙述片段 · ${narratorLines.value} 条`,
    mark: '旁',
    color: '#38bdf8',
    isNarrator: true,
    voiceId: map.get(0) ?? guessVoice('旁白'),
  }]
  store.roles.forEach((r, i) => {
    next.push({
      roleId: r.id,
      name: r.name,
      desc: `对话 ${r.line_count} 条${r.level === 'main' ? ' · 主角' : ''}`,
      mark: r.name.slice(0, 1),
      color: (r.profile?.color as string) || PALETTE[i % PALETTE.length],
      isNarrator: false,
      voiceId: map.get(r.id) ?? guessVoice(r.name),
    })
  })
  rows.value = next
}

/** 叙述 + 心理片段数（旁白台词量，设计稿写死 48 条） */
const narratorLines = computed(() => store.segments.filter(
  (s) => s.type === 'narration' || s.type === 'psychology',
).length)

/**
 * 按角色名猜音色：
 * 名字带女性指示词 → 优先「女声」标签；旁白 → 优先「旁白」标签；否则取第一个可用音色。
 * 猜不出来留 null，由用户在界面上补。
 */
function guessVoice(name: string): number | null {
  const has = (tag: string) => voices.value.find((v) => (v.tags || []).includes(tag))?.id ?? null
  if (name.includes('旁白')) return has('旁白')
  if (['她', '姐', '妹', '娘', '妻', '姑', '姨', '母', '女儿', '公主'].some((c) => name.includes(c))) {
    return has('女声') ?? roleVoices.value[0]?.id ?? null
  }
  return roleVoices.value[0]?.id ?? null
}

function voiceNameOf(id: number | null) {
  return voices.value.find((v) => v.id === id)?.name ?? ''
}

// ---------------------------------------------------------------- 动作
/** ⚡ 自动绑定：交给后端按音色标签匹配，再重拉一次行模型 */
async function autoBind() {
  autoBinding.value = true
  try {
    await bindingsApi.autoBind(props.workId)
    await load()
    ElMessage.success('已按音色标签自动绑定')
  } finally {
    autoBinding.value = false
  }
}

/** 重置全部：只清本地选择，不动后端（避免误触写坏已确认的绑定） */
function resetAll() {
  rows.value.forEach((r) => { r.voiceId = null })
}

/** 单角色试听：拿该角色绑定的音色合成一小段 */
async function preview(row: BindRow | undefined) {
  if (!row || row.voiceId == null) return
  const sample = `这是${row.name}的试听样本，语气与情绪都会跟随片段标注。`
  const res = await voicesApi.previewVoice(row.voiceId, sample, prosody.speed)
  previewUrl.value = res.audio_url
  const sec = Math.round(res.duration ?? 0)
  previewDuration.value = `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
}

/** 保存绑定：整体覆盖 + 顺手带上全局韵律参数，然后通知父组件进下一步 */
async function saveBind() {
  saving.value = true
  try {
    const items: Binding[] = rows.value.map((r) => ({
      role_id: r.roleId,
      voice_id: r.voiceId,
      params: { speed: prosody.speed, pitch: prosody.pitch, gain: prosody.gain, emotion_override: emotionOverride.value },
    }))
    await bindingsApi.setBindings(props.workId, items)
    ElMessage.success('绑定已保存')
    emit('next')
  } finally {
    saving.value = false
  }
}

onMounted(load)

defineExpose({ load })
</script>
