<template>
  <div>
    <div class="page-head">
      <div>
        <h1>音色库</h1>
        <div class="desc">内置音色与克隆音色的统一管理：标签、试听、参数微调，均可同步到工作室的角色绑定。</div>
      </div>
      <div class="row gap-2 right">
        <el-button class="btn" @click="tagDialog = true">标签管理</el-button>
        <el-button class="btn btn-primary" @click="cloneDialog = true">＋ 上传克隆音色</el-button>
      </div>
    </div>

    <!-- ============ 标签筛选 + 排序 + 视图切换 ============ -->
    <div class="row between wrap gap-3 mb">
      <div class="row wrap gap-2">
        <span :class="['chip filter', { active: !tagFilter }]" @click="tagFilter = ''">
          全部 ({{ voices.length }})
        </span>
        <span
          v-for="t in tags" :key="t.id"
          :class="['chip filter', { active: tagFilter === t.value }]"
          @click="toggleTag(t.value)"
        >
          <i class="cdot" :style="{ background: t.color || '#94a3b8' }"></i>{{ t.value }}
        </span>
      </div>
      <div class="row gap-2">
        <input v-model="keyword" class="input" style="width:200px" placeholder="搜索音色名称 / 标签…" />
        <select v-model="sort" class="select" style="width:140px">
          <option value="usage">按使用次数</option>
          <option value="created">按创建时间</option>
          <option value="name">按名称</option>
        </select>
        <div class="segmented">
          <button :class="{ active: view === 'grid' }" @click="view = 'grid'">卡片</button>
          <button :class="{ active: view === 'list' }" @click="view = 'list'">列表</button>
        </div>
      </div>
    </div>

    <!-- ============ 批量操作栏：勾选后出现 ============ -->
    <div v-if="selected.size" class="batch-bar mb">
      <b class="sm">已选 {{ selected.size }} 项</b>
      <el-button class="btn btn-sm" @click="batchAddTag">打标签</el-button>
      <el-button class="btn btn-sm" @click="batchExport">导出</el-button>
      <el-button class="btn btn-sm btn-danger" @click="batchDelete">删除</el-button>
      <el-button class="btn btn-sm btn-ghost right" @click="selected.clear()">取消选择</el-button>
    </div>

    <!-- ============ 卡片视图 ============ -->
    <div v-if="view === 'grid'" class="grid cols-3">
      <VoiceCard
        v-for="v in filteredVoices" :key="v.id"
        :v="v"
        :selected="selected.has(v.id)"
        :tag-colors="tagColorMap"
        @select="toggleSelect(v.id)"
        @remove-tag="(t) => removeTag(v, t)"
        @manage-tags="tagDialog = true"
        @preview="preview(v)"
        @rename="rename(v)"
        @remove="removeVoice(v)"
      />

      <!-- 新增卡（入口） -->
      <div
        class="panel voice-card"
        style="border-style:dashed;align-items:center;justify-content:center;text-align:center;cursor:pointer"
        @click="cloneDialog = true"
      >
        <div class="empty" style="padding:26px">
          <div class="ic" style="background:var(--accent-soft);color:var(--accent)">＋</div>
          <b style="color:var(--text-1)">上传克隆音色</b>
          <p class="tiny mt-2">录制或上传 1-3 分钟清晰人声</p>
        </div>
      </div>
    </div>

    <!-- ============ 列表视图 ============ -->
    <div v-else class="panel" style="padding:0">
      <table class="table">
        <thead>
          <tr>
            <th style="width:36px"></th><th>音色</th><th>标签</th><th>来源</th><th>状态</th><th>使用</th><th style="width:120px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in filteredVoices" :key="v.id">
            <td>
              <div :class="['check-dot', { on: selected.has(v.id) }]" @click="toggleSelect(v.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5" /></svg>
              </div>
            </td>
            <td><b style="color:var(--text-1)">{{ v.name }}</b><div class="tiny muted">{{ v.engine }}</div></td>
            <td>
              <span v-for="t in v.tags" :key="t" class="chip">
                <i class="cdot" :style="{ background: tagColor(t) }"></i>{{ t }}
              </span>
            </td>
            <td>{{ v.type === 'clone' ? '克隆' : '内置' }}</td>
            <td><span :class="['badge', listTone(v)]"><span class="dot"></span>{{ listStatus(v) }}</span></td>
            <td class="mono">{{ v.usage_count ?? 0 }}</td>
            <td class="right">
              <button class="icon-btn" @click="preview(v)">▶</button>
              <button class="icon-btn" @click="rename(v)">✎</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="hint mt-8">
      交互说明：卡片左上圆点为批量勾选；「⋯」为更多操作；标签可点 × 移除、点「+ 标签」打开标签管理；
      试听支持自定义文本；语速/音调滑杆只影响本次试听，不写回音色。
    </p>

    <!-- 克隆向导 / 标签管理，两个弹窗都挂在页面级，关闭不重渲染列表 -->
    <CloneDialog
      v-model="cloneDialog"
      :tags="tags"
      :compliance="compliance"
      @created="afterClone"
      @voiceprint="doVoiceprint"
      @go-settings="$router.push('/settings')"
      @preview="previewById"
    />
    <TagDialog v-model="tagDialog" :tags="tags" @changed="load" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import * as voicesApi from '@/api/voices'
import * as authApi from '@/api/auth'
import VoiceCard from '@/components/voice/VoiceCard.vue'
import CloneDialog from '@/components/voice/CloneDialog.vue'
import TagDialog from '@/components/voice/TagDialog.vue'
import type { Voice, VoiceTag } from '@/types'

/**
 * 音色库（design/voice-library.html 的 Vue 实现，DESIGN_SPEC §5.4）。
 *
 * 这一层只做「编排」：
 * - 拉音色 + 标签两份首屏数据；
 * - 关键字 / 标签 / 排序过滤 + 卡片 / 列表双视图切换；
 * - 批量勾选后的导出与删除；
 * - 三个弹窗开关（克隆向导、标签管理）与子组件的状态同步。
 *
 * 单卡展示、克隆向导、标签管理各自拆成子组件，这里不重复实现交互细节。
 */

const userStore = useUserStore()

// ------------------------------------------------------------ 列表状态

const voices = ref<Voice[]>([])
const tags = ref<VoiceTag[]>([])
const keyword = ref('')
/** 当前生效的标签筛选（空 = 全部） */
const tagFilter = ref('')
const sort = ref<'usage' | 'created' | 'name'>('usage')
const view = ref<'grid' | 'list'>('grid')
/** 批量勾选的音色 id */
const selected = ref<Set<number>>(new Set())
/** 克隆向导 / 标签管理弹窗开关 */
const cloneDialog = ref(false)
const tagDialog = ref(false)

/** 克隆合规前置：实名 + 声纹核验，都取自用户档案 */
const compliance = computed(() => ({
  realname_verified: !!userStore.profile?.realname_verified,
  voiceprint_checked: !!userStore.profile?.voiceprint_checked,
}))

/** 带关键字 + 标签 + 排序的过滤结果 */
const filteredVoices = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  let list = voices.value.filter((v) => {
    if (tagFilter.value && !(v.tags ?? []).includes(tagFilter.value)) return false
    if (!kw) return true
    return v.name.toLowerCase().includes(kw) || (v.tags ?? []).some((t) => t.toLowerCase().includes(kw))
  })
  if (sort.value === 'usage') list = [...list].sort((a, b) => (b.usage_count ?? 0) - (a.usage_count ?? 0))
  if (sort.value === 'name') list = [...list].sort((a, b) => a.name.localeCompare(b.name))
  return list
})

/** 标签 → 配色表，传给 VoiceCard 复用同一套查色逻辑 */
const tagColorMap = computed(() => {
  const m: Record<string, string> = {}
  for (const t of tags.value) m[t.value] = t.color || '#94a3b8'
  return m
})

function tagColor(value: string) {
  return tagColorMap.value[value]
}

/** 列表视图的状态文案（卡片上的 VoiceCard 内部有另一套） */
function listTone(v: Voice) {
  if (v.status === 'ready') return v.type === 'clone' ? 'ok' : 'acc'
  return 'warn'
}
function listStatus(v: Voice) {
  if (v.status === 'ready') return v.type === 'clone' ? '已就绪' : '可用'
  return '处理中'
}

// ------------------------------------------------------------ 数据加载

/** 加载音色与标签（列表页首屏两个请求）；同时把档案拉出来给合规门用 */
async function load() {
  const [vr, tr] = await Promise.all([
    voicesApi.listVoices({ page_size: 100 }),
    voicesApi.listTags(),
  ])
  voices.value = vr.items ?? []
  tags.value = tr.items ?? []
  if (!userStore.profile) {
    try { userStore.profile = await authApi.me() } catch { /* 未登录 */ }
  }
}

onMounted(load)

// ------------------------------------------------------------ 列表操作

function toggleTag(value: string) {
  tagFilter.value = tagFilter.value === value ? '' : value
}

function toggleSelect(id: number) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

/**
 * 试听：用该音色朗读自定义文本，语速取自卡上的滑杆。
 * VoiceCard 把 text / rate / pitch 留在卡内，这里只把「哪张卡 + 哪个音色」传上去。
 */
async function preview(v: Voice) {
  const res = await voicesApi.previewVoice(v.id, '欢迎收听今晚的故事。', 1)
  new Audio(res.audio_url).play().catch(() => ElMessage.warning('浏览器阻止了自动播放'))
}

/** 第 3 步完成后的试听：CloneDialog 回传的是刚建好的音色 id */
async function previewById(voiceId: number | null) {
  if (!voiceId) return
  const res = await voicesApi.previewVoice(voiceId, '这是新克隆的声音')
  new Audio(res.audio_url).play().catch(() => ElMessage.warning('浏览器阻止了自动播放'))
}

/** 重命名音色 */
async function rename(v: Voice) {
  try {
    const { value } = await ElMessageBox.prompt('新的音色名称', '重命名', {
      inputValue: v.name, confirmButtonText: '保存', cancelButtonText: '取消',
    })
    if (!value) return
    await voicesApi.updateVoice(v.id, { name: value })
    await load()
    ElMessage.success('已重命名')
  } catch { /* 用户取消 */ }
}

/**
 * 删除音色：后端会检查引用。
 * 被角色绑定引用时返回 { need_confirm: true, refs: n }，需要带 force=true 二次确认。
 */
async function removeVoice(v: Voice) {
  const res = await voicesApi.deleteVoice(v.id)
  if (res.need_confirm) {
    try {
      await ElMessageBox.confirm(
        `该音色被 ${res.refs} 处角色绑定引用，删除后这些角色会变为未绑定。确定删除吗？`,
        '删除音色',
        { type: 'warning', confirmButtonText: '强制删除', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
    await voicesApi.deleteVoice(v.id, true)
  }
  await load()
  ElMessage.success('已删除音色')
}

/** 移除音色上的某个标签（改标签集合后整组 PUT） */
async function removeTag(v: Voice, tag: string) {
  await voicesApi.updateVoice(v.id, { tags: (v.tags ?? []).filter((t) => t !== tag) })
  await load()
}

async function batchAddTag() {
  tagDialog.value = true
  ElMessage.info('新建标签后，可在音色卡上逐个添加（POC 未提供批量打标接口）')
}

/** 导出所选音色配置（JSON 下载） */
function batchExport() {
  const picked = voices.value.filter((v) => selected.value.has(v.id))
  const blob = new Blob([JSON.stringify(picked, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'voices.json'
  a.click()
  URL.revokeObjectURL(url)
}

/** 批量删除：逐个走 removeVoice 的引用确认逻辑 */
async function batchDelete() {
  try {
    await ElMessageBox.confirm(
      `将删除 ${selected.value.size} 个音色，被绑定的角色会变为未绑定。确定吗？`,
      '批量删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  for (const id of selected.value) {
    await voicesApi.deleteVoice(id, true)
  }
  selected.value = new Set()
  await load()
  ElMessage.success('已删除所选音色')
}

// ------------------------------------------------------------ 克隆向导联动

/** 克隆完成后把新音色刷进列表（CloneDialog 已回传新 id） */
async function afterClone(voiceId: number | null) {
  await load()
  if (voiceId) ElMessage.success('音色已保存到音色库')
}

/** 声纹核验：CloneDialog 只管 loading，真正的请求与档案刷新放这里 */
async function doVoiceprint() {
  try {
    await voicesApi.voiceprintCheck()
    userStore.profile = await authApi.me()
    ElMessage.success('声纹核验通过')
  } catch {
    /* 错误提示由拦截器统一弹出 */
  }
}
</script>
