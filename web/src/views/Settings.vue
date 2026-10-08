<template>
  <div>
    <div class="page-head">
      <div>
        <h1>账户与偏好</h1>
        <div class="desc">个人信息、克隆合规前置、默认偏好与安全设置。</div>
      </div>
    </div>

    <div class="grid cols-2">
      <!-- 1. 基本信息 -->
      <div class="panel mb">
        <div class="card-h"><h3>基本信息</h3></div>
        <div class="row gap-4 mb">
          <div class="avatar" style="width:64px;height:64px;border-radius:16px;background:var(--grad);font-size:22px">
            {{ mark }}
          </div>
          <div class="col gap-2">
            <el-button class="btn btn-sm" @click="ElMessage.info('POC 未接对象存储，头像暂不可上传')">
              更换头像
            </el-button>
            <span class="tiny muted">支持 PNG / JPG，≤ 2MB</span>
          </div>
        </div>
        <div class="grid cols-2">
          <div class="field"><label class="label">昵称</label>
            <input v-model="form.nickname" class="input" />
          </div>
          <div class="field"><label class="label">邮箱</label>
            <input v-model="form.email" class="input" disabled />
          </div>
        </div>
        <el-button class="btn btn-primary" :loading="savingProfile" @click="saveProfile">保存修改</el-button>
      </div>

      <!-- 2. 克隆合规前置（声音克隆的前置条件，音色库会回跳到这里） -->
      <div class="panel mb">
        <div class="card-h"><h3>克隆合规前置</h3><span class="sub">全部通过才可提交克隆</span></div>
        <div class="compliance">
          <span :class="['ci', { pass: profile?.realname_verified }]">实名认证 {{ profile?.realname_verified ? '✓' : '未' }}</span>
          <span class="ci pass">授权书 ✓</span>
          <span :class="['ci', { pass: profile?.voiceprint_checked }]">声纹核验 {{ profile?.voiceprint_checked ? '✓' : '未' }}</span>
          <span class="ci pass">禁公众人物 ✓</span>
          <span class="ci pass">隐式水印 ✓</span>
        </div>

        <!-- 未实名：填姓名 / 证件号 / 授权书 -->
        <template v-if="!profile?.realname_verified">
          <div class="grid cols-2 mt">
            <div class="field"><label class="label">真实姓名</label>
              <input v-model="realnameForm.real_name" class="input" placeholder="与证件一致" />
            </div>
            <div class="field"><label class="label">证件号</label>
              <input v-model="realnameForm.id_card_no" class="input" placeholder="身份证号" />
            </div>
          </div>
          <div class="field"><label class="label">授权书 URL（已签署并上传）</label>
            <input v-model="realnameForm.consent_doc_url" class="input" placeholder="https://…/consent.pdf" />
          </div>
          <el-button class="btn btn-primary" :loading="verifying" @click="doRealname">提交实名认证</el-button>
        </template>

        <!-- 已实名未声纹：一键核验（POC 免真实比对） -->
        <div v-else-if="!profile?.voiceprint_checked" class="row between mt">
          <span class="tiny muted">实名已通过，还需确认「本人」才能克隆</span>
          <el-button class="btn btn-primary btn-sm" :loading="checking" @click="doVoiceprint">做声纹核验</el-button>
        </div>

        <div v-else class="row between mt">
          <span class="tiny muted">两项前置均已通过，可以去音色库上传克隆</span>
          <el-button class="btn btn-sm" @click="$router.push('/voices')">去音色库 →</el-button>
        </div>
        <p class="hint">POC 阶段只做必填校验，未接第三方实名 / 声纹比对；生产需替换为真实核验服务。</p>
      </div>

      <!-- 3. 创作偏好（本地保存，作为新建作品的默认值） -->
      <div class="panel mb">
        <div class="card-h"><h3>创作偏好</h3><span class="sub">新建作品时的默认值</span></div>
        <div class="grid cols-2">
          <div class="field"><label class="label">默认旁白音色</label>
            <select v-model="pref.narrator" class="select">
              <option v-for="v in voices" :key="v.id" :value="v.name">{{ v.name }}</option>
            </select>
          </div>
          <div class="field"><label class="label">默认合成范围</label>
            <select v-model="pref.scope" class="select">
              <option value="sample">样章先行（前 2 章）</option>
              <option value="full">全本合成</option>
            </select>
          </div>
          <div class="field"><label class="label">情绪识别方式</label>
            <select v-model="pref.emotion" class="select">
              <option value="heuristic">标点启发式（POC）</option>
              <option value="llm">LLM 增强（生产）</option>
            </select>
          </div>
          <div class="field"><label class="label">音频格式</label>
            <select v-model="pref.format" class="select">
              <option value="wav">WAV（无损）</option>
              <option value="mp3">MP3 128k</option>
            </select>
          </div>
        </div>
        <label class="row gap-2 sm" style="cursor:pointer">
          <input v-model="pref.autoPlay" type="checkbox" /> 样章合成完成后自动试听
        </label>
        <div class="mt">
          <el-button class="btn btn-primary" @click="savePref">保存偏好</el-button>
        </div>
        <p class="hint">偏好只存在本机（localStorage），POC 未提供用户配置接口。</p>
      </div>

      <!-- 4. 安全 -->
      <div class="panel">
        <div class="card-h"><h3>安全</h3></div>
        <div class="grid cols-2">
          <div class="field"><label class="label">当前密码</label>
            <input v-model="pwd.old" class="input" type="password" placeholder="••••••••" />
          </div>
          <div class="field"><label class="label">新密码</label>
            <input v-model="pwd.next" class="input" type="password" placeholder="至少 8 位" />
          </div>
        </div>
        <el-button class="btn" :loading="savingPwd" @click="savePassword">修改密码</el-button>
        <hr class="divider" />
        <div class="row between">
          <div><b class="sm">退出登录</b><p class="tiny muted">清除本机会话凭证</p></div>
          <el-button class="btn btn-danger" @click="doLogout">退出</el-button>
        </div>

        <hr class="divider" />
        <div class="card-h"><h3>关于</h3></div>
        <div class="row between sm"><span class="muted">版本</span><span class="mono tiny">v0.1.0-poc</span></div>
        <div class="row between sm mt-2">
          <span class="muted">TTS 引擎</span>
          <span class="badge warn"><span class="dot"></span>Stub（POC 占位）</span>
        </div>
        <div class="row between sm mt-2">
          <span class="muted">克隆合规</span>
          <span :class="['badge', complianceOk ? 'ok' : 'warn']">
            <span class="dot"></span>{{ complianceOk ? '已通过' : '待完成' }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import * as authApi from '@/api/auth'
import * as voicesApi from '@/api/voices'
import type { Voice } from '@/types'

/**
 * 设置页（design/settings.html 的 Vue 实现）。
 *
 * 四块：基本信息（昵称走 PATCH /auth/me）、克隆合规前置（实名 + 声纹核验）、
 * 创作偏好（本地 localStorage）、安全（改密码 + 退出登录）。
 * 音色库的「去实名认证」会跳转到本页，因此合规块要放在显眼位置。
 */

const router = useRouter()
const userStore = useUserStore()

/** 偏好在 localStorage 的键名 */
const PREF_KEY = 'sb_prefs'

const profile = computed(() => userStore.profile)
const mark = computed(() => (profile.value?.nickname || profile.value?.email || 'U').slice(0, 1).toUpperCase())
const complianceOk = computed(
  () => !!profile.value?.realname_verified && !!profile.value?.voiceprint_checked,
)

const form = reactive({ nickname: '', email: '' })
const savingProfile = ref(false)

const realnameForm = reactive({ real_name: '', id_card_no: '', consent_doc_url: '' })
const verifying = ref(false)
const checking = ref(false)

/** 创作偏好：默认值与设计稿一致，读不到时用这套 */
const pref = reactive({
  narrator: '旁白 · 中性',
  scope: 'sample',
  emotion: 'heuristic',
  format: 'mp3',
  autoPlay: true,
})

const pwd = reactive({ old: '', next: '' })
const savingPwd = ref(false)

/** 默认旁白音色下拉的可选项 */
const voices = ref<Voice[]>([])

onMounted(async () => {
  if (!userStore.profile) {
    try { userStore.profile = await authApi.me() } catch { /* 未登录 */ }
  }
  const p = userStore.profile
  form.nickname = p?.nickname ?? ''
  form.email = p?.email ?? ''
  loadPref()
  try {
    const res = await voicesApi.listVoices({ page_size: 100 })
    voices.value = res.items ?? []
  } catch { /* 音色库不可用时不阻塞设置页 */ }
})

/** 读取本机偏好（没有就用默认值） */
function loadPref() {
  try {
    const raw = localStorage.getItem(PREF_KEY)
    if (raw) Object.assign(pref, JSON.parse(raw))
  } catch {
    /* 解析失败就用默认值 */
  }
}

// ------------------------------------------------------------ 动作

async function saveProfile() {
  savingProfile.value = true
  try {
    const updated = await authApi.updateMe({ nickname: form.nickname })
    userStore.profile = updated
    ElMessage.success('资料已保存')
  } finally {
    savingProfile.value = false
  }
}

/** 提交实名认证（POC 只校验必填） */
async function doRealname() {
  if (!realnameForm.real_name || !realnameForm.id_card_no) {
    ElMessage.warning('请填写真实姓名与证件号')
    return
  }
  if (!realnameForm.consent_doc_url) {
    ElMessage.warning('请先签署授权书并上传')
    return
  }
  verifying.value = true
  try {
    await voicesApi.realnameVerify({
      real_name: realnameForm.real_name,
      id_card_no: realnameForm.id_card_no,
      consent_doc_url: realnameForm.consent_doc_url,
    })
    userStore.profile = await authApi.me()
    ElMessage.success('实名认证已通过')
  } finally {
    verifying.value = false
  }
}

/** 声纹核验：POC 免真实比对 */
async function doVoiceprint() {
  checking.value = true
  try {
    await voicesApi.voiceprintCheck()
    userStore.profile = await authApi.me()
    ElMessage.success('声纹核验已通过')
  } finally {
    checking.value = false
  }
}

function savePref() {
  localStorage.setItem(PREF_KEY, JSON.stringify(pref))
  ElMessage.success('偏好已保存到本机')
}

async function savePassword() {
  if (!pwd.old || pwd.next.length < 8) {
    ElMessage.warning('请填写当前密码，且新密码至少 8 位')
    return
  }
  savingPwd.value = true
  try {
    await authApi.changePassword({ old_password: pwd.old, new_password: pwd.next })
    pwd.old = ''
    pwd.next = ''
    ElMessage.success('密码已更新')
  } finally {
    savingPwd.value = false
  }
}

/** 退出登录：清本地凭证并跳登录页 */
async function doLogout() {
  try { await authApi.logout() } catch { /* 后端无状态时忽略 */ }
  userStore.logout()
  router.push('/login')
}
</script>
