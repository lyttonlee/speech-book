<template>
  <div class="panel">
    <div class="card-h">
      <h3>角色与声纹绑定</h3>
      <span class="sub">每行 = 一位说话人 · 字段都可改，改动只触发增量重合成</span>
    </div>

    <div class="row gap-2 mb">
      <el-button class="btn btn-primary btn-sm" :loading="store.isSaving('binding:auto')" @click="onAutoBind">
        ⚡ 自动匹配
      </el-button>
      <el-button class="btn btn-sm" :loading="store.isSaving('binding:all')" @click="saveAll">
        保存全部绑定
      </el-button>
      <div style="flex:1"></div>
      <span class="tiny muted">
        未绑定 {{ unboundCount }} / {{ roles.length }} · 低置信 {{ lowConfCount }}
      </span>
    </div>

    <!-- 绑定行：角色名 / 音色 / 语速 / 音高 / 置信 / 操作 -->
    <div class="bind-wrap">
      <div
        v-for="r in roles"
        :key="r.id"
        :class="['bind-row', rowClass(r)]"
      >
        <!-- 角色 -->
        <div class="b-role">
          <div class="avatar" :style="{ background: roleColor(r) }">{{ r.name.slice(0, 1) }}</div>
          <div style="min-width:0">
            <div class="b-name">
              {{ r.name }}
              <span class="tag">{{ levelText(r.level) }}</span>
              <!-- 已人工介入角标 -->
              <span v-if="isAdjusted(r.id)" class="adj-dot" title="已人工介入"></span>
            </div>
            <div class="tiny muted">{{ r.line_count }} 段台词</div>
          </div>
        </div>

        <!-- 音色 -->
        <div class="b-voice">
          <select
            v-model="form[r.id].voice_id"
            class="select"
            @change="markDirty(r.id)"
          >
            <option :value="null">未绑定</option>
            <option v-for="v in voices" :key="v.id" :value="v.id">{{ v.name }}</option>
          </select>
        </div>

        <!-- 语速 -->
        <div class="b-param">
          <span class="tiny muted">语速</span>
          <input
            v-model.number="form[r.id].speed"
            type="range" min="0.5" max="2" step="0.05"
            class="slider"
            @input="markDirty(r.id)"
          />
          <span class="pv">{{ form[r.id].speed.toFixed(2) }}</span>
        </div>

        <!-- 音高 -->
        <div class="b-param">
          <span class="tiny muted">音高</span>
          <input
            v-model.number="form[r.id].pitch"
            type="range" min="-0.5" max="0.5" step="0.02"
            class="slider"
            @input="markDirty(r.id)"
          />
          <span class="pv">{{ form[r.id].pitch.toFixed(2) }}</span>
        </div>

        <!-- 置信 -->
        <div class="b-conf">
          <span class="conf-bar" :class="{ low: isLowConf(r) }">
            <i :style="{ width: confWidth(r) + '%' }"></i>
          </span>
          <span class="cv">{{ confText(r) }}</span>
        </div>

        <!-- 操作 -->
        <div class="b-ops">
          <el-button class="btn btn-sm" @click="preview(r)">试听</el-button>
          <el-button
            v-if="dirty.has(r.id)"
            class="btn btn-primary btn-sm"
            :loading="store.isSaving(`binding:${r.id}`)"
            @click="saveRow(r)"
          >保存</el-button>
          <span v-else class="tiny muted">已保存</span>
        </div>
      </div>

      <!-- 未绑定提示：一键补绑 -->
      <div v-if="unboundCount" class="notice warn mt-2">
        还有 {{ unboundCount }} 位角色没绑定音色。
        <a href="javascript:;" class="lnk" @click="onAutoBind">一键补绑 →</a>
      </div>
    </div>

    <!-- 角色操作：合并 / 降为龙套 / 删除 -->
    <div class="card-h mt-2">
      <h3 style="font-size:14px">角色操作</h3>
      <span class="sub">合并把来源角色的台词改挂到目标；删除为破坏性操作，需二次确认</span>
    </div>
    <div class="row gap-2 wrap">
      <select v-model="mergeTarget" class="select" style="width:160px">
        <option :value="null">合并到…</option>
        <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
      </select>
      <select v-model="mergeSource" class="select" style="width:160px">
        <option :value="null">来源角色</option>
        <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
      </select>
      <el-button class="btn btn-sm" :disabled="!canMerge" @click="doMerge">合并</el-button>
      <div style="flex:1"></div>
      <el-button class="btn btn-danger btn-sm" @click="doDeleteRole">删除角色</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import * as voicesApi from '@/api/voices'
import * as rolesApi from '@/api/roles'
import type { Binding, Role, Voice } from '@/types'

const props = defineProps<{ workId: number; roles: Role[]; bindings: Binding[] }>()

const store = useWorkStore()

/** 音色下拉选项 */
const voices = ref<Voice[]>([])
/** 行内编辑表单：roleId -> { voice_id, speed, pitch } */
const form = reactive<Record<number, { voice_id: number | null; speed: number; pitch: number }>>({})
/** 哪些行被改过还没保存 */
const dirty = ref<Set<number>>(new Set())

const mergeTarget = ref<number | null>(null)
const mergeSource = ref<number | null>(null)

const roles = computed(() => props.roles ?? [])
const bindingOf = computed(() => {
  const m: Record<number, Binding> = {}
  for (const b of props.bindings ?? []) m[b.role_id] = b
  return m
})

const unboundCount = computed(() => roles.value.filter((r) => !form[r.id]?.voice_id).length)
const lowConfCount = computed(() => roles.value.filter(isLowConf).length)
const canMerge = computed(() => mergeTarget.value && mergeSource.value && mergeTarget.value !== mergeSource.value)

// ------------------------------------------------------------ 表单同步

/** 把后端绑定数据铺进表单（切换书或刷新后调用） */
function syncForm() {
  for (const r of roles.value) {
    const b = bindingOf.value[r.id]
    const p = (b?.params ?? {}) as Record<string, number>
    form[r.id] = {
      voice_id: b?.voice_id ?? null,
      speed: typeof p.speed === 'number' ? p.speed : 1.0,
      pitch: typeof p.pitch === 'number' ? p.pitch : 0,
    }
  }
  dirty.value = new Set()
}

watch(() => [props.roles, props.bindings], syncForm, { immediate: true, deep: true })

/** 加载音色下拉（POC 三个内置 + 用户克隆） */
async function loadVoices() {
  const res = await voicesApi.listVoices({ page_size: 100 })
  voices.value = res.items ?? []
}

// ------------------------------------------------------------ 视觉映射

function roleColor(r: Role) {
  // 用 id 做稳定散列取色，避免每次刷新颜色乱跳
  const palette = ['#38bdf8', '#6366f1', '#22d3ee', '#fbbf24', '#fb7185', '#34d399']
  return palette[r.id % palette.length]
}

function levelText(level: string) {
  return { main: '主角', supporting: '配角', extra: '龙套' }[level] ?? level
}

/** 行状态：未绑定 → 橙边框；低置信 → 红边框（DESIGN_SPEC §7b.3 视觉编码） */
function rowClass(r: Role) {
  if (!form[r.id]?.voice_id) return 'unbound'
  if (isLowConf(r)) return 'lowconf'
  return ''
}

/** 角色置信度取自画像 profile.confidence，缺失时按台词数粗判 */
function confOf(r: Role): number {
  const c = (r.profile ?? {}).confidence
  if (typeof c === 'number') return c
  return r.line_count >= 3 ? 0.9 : 0.6
}

function isLowConf(r: Role) {
  return confOf(r) < 0.7
}

function confWidth(r: Role) {
  return Math.round(confOf(r) * 100)
}

function confText(r: Role) {
  return confOf(r).toFixed(2)
}

/** 该角色是否被人工改过（从留痕里查） */
function isAdjusted(roleId: number) {
  return store.edits.some((e) => e.object_type === 'role' && e.object_id === roleId)
}

// ------------------------------------------------------------ 动作

function markDirty(roleId: number) {
  dirty.value = new Set(dirty.value).add(roleId)
}

/** 保存单行：走 store 的保存包装器，UI 有「保存中 → 已保存」反馈 */
async function saveRow(r: Role) {
  const f = form[r.id]
  await store.setBindings(props.workId, [{
    role_id: r.id,
    voice_id: f.voice_id,
    params: { speed: f.speed, pitch: f.pitch },
  }])
  dirty.value = new Set([...dirty.value].filter((id) => id !== r.id))
  ElMessage.success('已保存 · 已记入修改日志')
}

/** 保存所有改过的行 */
async function saveAll() {
  const items = [...dirty.value].map((id) => ({
    role_id: id,
    voice_id: form[id].voice_id,
    params: { speed: form[id].speed, pitch: form[id].pitch },
  }))
  if (!items.length) {
    // 没改动时把当前全部行提交一遍，保证旁白等固定项也落库
    items.push(...roles.value.map((r) => ({
      role_id: r.id,
      voice_id: form[r.id].voice_id,
      params: { speed: form[r.id].speed, pitch: form[r.id].pitch },
    })))
  }
  await store.setBindings(props.workId, items)
  dirty.value = new Set()
  ElMessage.success('已保存全部绑定')
}

async function onAutoBind() {
  await store.autoBind(props.workId)
  ElMessage.success('已按音色标签自动匹配')
}

/** 用该角色当前绑定音色试听一段示例文本 */
async function preview(r: Role) {
  const vid = form[r.id]?.voice_id
  if (!vid) {
    ElMessage.warning('该角色还没绑定音色')
    return
  }
  const res = await voicesApi.previewVoice(vid, `${r.name}的台词示例`, form[r.id].speed)
  // 交给常驻迷你播放器全局抢占试听
  new Audio(res.audio_url).play().catch(() => ElMessage.warning('浏览器阻止了自动播放'))
}

/** 合并角色：把来源角色的台词改挂到目标角色 */
async function doMerge() {
  if (!canMerge.value) return
  try {
    await ElMessageBox.confirm('合并后来源角色会被移除，台词全部改挂到目标角色。确定吗？', '合并角色', { type: 'warning' })
  } catch {
    return
  }
  await rolesApi.mergeRoles(props.workId, mergeTarget.value!, [mergeSource.value!])
  await store.loadOverview(props.workId)
  ElMessage.success('已合并角色')
}

/** 删除角色：破坏性操作，二次确认（DESIGN_SPEC §7b.3） */
async function doDeleteRole() {
  if (!mergeSource.value) {
    ElMessage.warning('请先在「来源角色」里选择要删除的角色')
    return
  }
  const target = roles.value.find((r) => r.id === mergeSource.value)
  try {
    await ElMessageBox.confirm(`删除角色「${target?.name}」后，其台词会变为未归属。确定删除吗？`, '删除角色', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await rolesApi.deleteRole(props.workId, mergeSource.value!)
  await store.loadOverview(props.workId)
  ElMessage.success('已删除角色')
}

loadVoices()
</script>

<style scoped>
.bind-wrap { display: flex; flex-direction: column; gap: 10px; }

.bind-row {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr 1fr 0.9fr auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: var(--r-sm);
  background: var(--bg-2);
}

/* 视觉编码：未绑定=橙左边框，低置信=红左边框 */
.bind-row.unbound { border-left: 3px solid var(--warn); }
.bind-row.lowconf { border-left: 3px solid var(--danger); }

@media (max-width: 1080px) {
  .bind-row { grid-template-columns: 1fr 1fr; }
}

.b-role { display: flex; align-items: center; gap: 10px; min-width: 0; }
.b-name { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.b-param { display: flex; align-items: center; gap: 8px; }
.b-param .slider { width: 84px; }
.pv { font-family: var(--mono, monospace); font-size: 12px; color: var(--text-2); width: 34px; }
.b-conf { display: flex; align-items: center; gap: 8px; }
.b-ops { display: flex; align-items: center; gap: 8px; }

/* 已人工介入角标 */
.adj-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--warn); display: inline-block;
}
.lnk { color: var(--accent); text-decoration: none; }
</style>
