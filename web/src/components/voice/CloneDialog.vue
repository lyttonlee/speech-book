<template>
  <div v-if="modelValue" class="modal-mask" @click.self="close">
    <div class="modal modal-lg">
      <div class="modal-head">
        <h3>上传克隆音色</h3>
        <span class="badge warn"><span class="dot"></span>POC 占位</span>
        <button class="modal-close" @click="close">✕</button>
      </div>

      <div class="modal-body">
        <!-- 向导步骤条 -->
        <div class="row gap-6" style="margin-bottom:20px">
          <div v-for="(s, i) in CLONE_STEPS" :key="s.key" :class="['vstep', stepClass(i + 1)]">
            <div class="vdot">{{ i + 1 }}</div>
            <div class="vtxt"><b>{{ s.title }}</b><span>{{ s.desc }}</span></div>
          </div>
        </div>

        <!-- 第 1 步：合规前置 + 样本信息 -->
        <div v-if="step === 1">
          <!-- 合规前置清单：未通过不允许提交 -->
          <div class="card mb" style="border-color:rgba(251,191,36,.3)">
            <b class="sm">克隆合规前置（全部通过才可提交）</b>
            <div class="compliance mt-2">
              <span :class="['ci', { pass: compliance.realname_verified }]">
                实名认证 {{ compliance.realname_verified ? '✓' : '未' }}
              </span>
              <span class="ci pass">授权书 ✓</span>
              <span :class="['ci', { pass: compliance.voiceprint_checked }]">
                声纹核验 {{ compliance.voiceprint_checked ? '✓' : '未' }}
              </span>
              <span class="ci pass">禁公众人物 ✓</span>
              <span class="ci pass">隐式水印 ✓</span>
            </div>
            <div class="row gap-2 mt-2">
              <el-button
                v-if="!compliance.realname_verified"
                class="btn btn-sm"
                @click="emit('go-settings')"
              >去实名认证</el-button>
              <el-button
                v-if="compliance.realname_verified && !compliance.voiceprint_checked"
                class="btn btn-sm" :loading="checking"
                @click="emit('voiceprint')"
              >做声纹核验</el-button>
            </div>
          </div>

          <div class="grid cols-2">
            <div class="field"><label class="label">音色名称</label>
              <input v-model="form.name" class="input" placeholder="例如：我的声音 v2" />
            </div>
            <div class="field"><label class="label">声线类型</label>
              <select v-model="form.tone" class="select">
                <option value="男声">男声</option><option value="女声">女声</option><option value="中性">中性</option>
              </select>
            </div>
          </div>

          <div class="field">
            <label class="label">样本音频 URL（POC：填已上传音频的地址）</label>
            <input v-model="form.sampleUrl" class="input" placeholder="https://…/sample.wav" />
          </div>

          <div class="field">
            <label class="label">初始标签</label>
            <div class="row wrap gap-2">
              <span
                v-for="t in tags" :key="t.id"
                :class="['chip filter', { active: form.tags.includes(t.value) }]"
                @click="toggleTag(t.value)"
              >
                <i class="cdot" :style="{ background: t.color || '#94a3b8' }"></i>{{ t.value }}
              </span>
            </div>
          </div>

          <div class="card mt" style="border-color:rgba(251,191,36,0.3)">
            <b class="sm">样本要求（影响克隆质量）</b>
            <ul class="tiny muted" style="margin:8px 0 0;padding-left:18px;line-height:2">
              <li>环境安静、无背景音乐与混响</li>
              <li>单人连续说话，语速自然</li>
              <li>内容不限，建议 ≥ 60 秒（上限 3 分钟）</li>
              <li>请确认你拥有该声音的合法权利</li>
            </ul>
          </div>
        </div>

        <!-- 第 2 步：处理中 -->
        <div v-else-if="step === 2">
          <div class="dropzone" style="cursor:default">
            <b style="color:var(--text-1)">正在提取音色特征…</b>
            <div class="progress" style="margin:16px 0"><i :style="{ width: progress + '%' }"></i></div>
            <p class="tiny muted">可关闭窗口，完成后刷新列表即可看到新音色。</p>
          </div>
          <div class="card mt">
            <b class="sm">处理流水</b>
            <div class="col gap-2 mt-2 tiny">
              <div class="row between"><span class="muted">1. 音频预处理（降噪 / 切分）</span><span style="color:var(--ok)">完成</span></div>
              <div class="row between"><span class="muted">2. 特征提取（音色 embedding）</span><span style="color:var(--accent)">进行中 {{ progress }}%</span></div>
              <div class="row between"><span class="muted">3. 声学模型注册</span><span class="muted">等待</span></div>
              <div class="row between"><span class="muted">4. 质量校验（试听样例生成）</span><span class="muted">等待</span></div>
            </div>
          </div>
        </div>

        <!-- 第 3 步：完成 -->
        <div v-else>
          <div class="row gap-4 mb">
            <div class="avatar" style="width:56px;height:56px;border-radius:14px;background:var(--ok);font-size:20px;display:grid;place-items:center;color:#052012;font-weight:700">
              {{ (form.name || '我').slice(0, 1) }}
            </div>
            <div>
              <b style="font-size:16px">「{{ form.name }}」克隆完成</b>
              <div class="tiny muted mt-2">建议先试听再回到作品里绑定角色</div>
            </div>
          </div>
          <div class="player">
            <button class="play" @click="emit('preview', newVoiceId)">▶</button>
            <div class="wave">
              <i v-for="(h, i) in wave" :key="i" :style="{ height: h + '%' }"></i>
            </div>
            <div class="time">00:00 / 00:20</div>
          </div>
        </div>
      </div>

      <div class="modal-foot">
        <el-button class="btn btn-ghost" @click="close">取消</el-button>
        <el-button
          v-if="step === 1"
          class="btn btn-primary" :disabled="!canSubmit"
          @click="submit"
        >下一步：开始处理</el-button>
        <el-button v-else-if="step === 2" class="btn btn-primary" @click="step = 3">跳过等待，查看结果</el-button>
        <el-button v-else class="btn btn-primary" @click="finish">完成</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import * as voicesApi from '@/api/voices'
import * as authApi from '@/api/auth'
import type { VoiceTag } from '@/types'

/**
 * 上传克隆音色三步向导（design/voice-library.html 的 #modal-upload）。
 *
 * 第 1 步强制卡合规：实名 + 声纹核验都通过、且名称与样本都填了，
 * 才允许点「下一步」（后端同样会校验，这里先挡一道省一次无效请求）。
 * 第 2 步的进度是本地模拟的，生产换成克隆任务轮询或 SSE。
 */

const props = defineProps<{
  /** 弹窗开关（v-model） */
  modelValue: boolean
  tags: VoiceTag[]
  /** 合规前置状态，由父组件从用户档案派生后传入 */
  compliance: { realname_verified: boolean; voiceprint_checked: boolean }
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  /** 克隆完成，回传新音色 id，父组件据此刷新列表 */
  created: [voiceId: number | null]
  /** 声纹核验：交给父组件发请求，弹窗只管 loading */
  voiceprint: []
  /** 去设置页实名 */
  'go-settings': []
  /** 第 3 步试听 */
  preview: [voiceId: number | null]
}>()

const CLONE_STEPS = [
  { key: 'sample', title: '选择样本', desc: '上传或录制' },
  { key: 'process', title: '处理中', desc: '提取音色特征' },
  { key: 'done', title: '完成', desc: '试听并保存' },
]

const step = ref(1)
const progress = ref(0)
const checking = ref(false)
const newVoiceId = ref<number | null>(null)
const form = reactive({ name: '', tone: '男声', sampleUrl: '', tags: [] as string[] })
/** 本地进度轮询句柄，关闭 / 卸载都要清掉，否则定时器会挂在后台跑 */
let timer: number | undefined

/** 提交前置：名称 + 样本 + 合规三项必须都满足 */
const canSubmit = computed(
  () =>
    !!form.name.trim() && !!form.sampleUrl.trim()
    && props.compliance.realname_verified && props.compliance.voiceprint_checked,
)

const wave = computed(() => Array.from({ length: 46 }, (_, i) => 18 + Math.abs(Math.sin(i * 0.45)) * 70))

/** 步骤指示：之前的 done，当前的 active */
function stepClass(n: number) {
  if (n < step.value) return 'done'
  if (n === step.value) return 'active'
  return ''
}

function toggleTag(value: string) {
  const i = form.tags.indexOf(value)
  if (i >= 0) form.tags.splice(i, 1)
  else form.tags.push(value)
}

/** 关弹窗：顺手停掉进度轮询 */
function close() {
  stopTimer()
  emit('update:modelValue', false)
  reset()
}

/** 点「完成」：同样是关闭，但要把新音色 id 回抛给父组件刷新列表 */
function finish() {
  stopTimer()
  emit('update:modelValue', false)
  emit('created', newVoiceId.value)
  reset()
}

function stopTimer() {
  if (timer) {
    window.clearInterval(timer)
    timer = undefined
  }
}

/** 重开 / 关闭后回到第 1 步的初始状态 */
function reset() {
  stopTimer()
  step.value = 1
  progress.value = 0
  newVoiceId.value = null
  form.name = ''
  form.tone = '男声'
  form.sampleUrl = ''
  form.tags = []
}

/** 每次打开都把档案拉一次，保证合规状态是最新的 */
watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    step.value = 1
    const userStore = useUserStore()
    if (!userStore.profile) {
      try {
        userStore.profile = await authApi.me()
      } catch {
        /* 未登录就忽略，合规项显示为未通过 */
      }
    }
  },
)

/**
 * 提交克隆：后端在合规不通过时抛 422 CLONE_COMPLIANCE_FAILED / BANNED_PERSON，
 * 错误提示由 request 拦截器统一弹出，这里不用重复处理。
 */
async function submit() {
  if (!canSubmit.value) {
    ElMessage.warning('请先完成实名认证与声纹核验')
    return
  }
  const res = await voicesApi.submitClone(form.name.trim(), form.sampleUrl.trim())
  newVoiceId.value = res.voice_id ?? null
  step.value = 2
  progress.value = 0
  timer = window.setInterval(() => {
    progress.value = Math.min(100, progress.value + 8)
    if (progress.value >= 100) {
      stopTimer()
      // 进度满后自动进第三步
      step.value = 3
    }
  }, 400)
}

onBeforeUnmount(stopTimer)
</script>
