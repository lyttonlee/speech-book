<template>
  <div class="panel voice-card">
    <div class="row gap-3">
      <!-- 批量勾选圆点 -->
      <div :class="['check-dot', { on: selected }]" @click="emit('select')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      </div>
      <div class="avatar" :style="{ width: '42px', height: '42px', fontSize: '15px', background: avatarColor }">
        {{ v.name.slice(0, 1) }}
      </div>
      <div style="min-width:0">
        <b>{{ v.name }}</b>
        <div class="tiny muted">{{ typeText }} · {{ v.engine }} · 使用 {{ v.usage_count ?? 0 }} 次</div>
      </div>
      <div class="right row gap-2">
        <span :class="['badge', tone]"><span class="dot"></span>{{ statusText }}</span>
        <div class="menu-wrap">
          <button class="menu-btn" @click="openMenuId = openMenuId === v.id ? null : v.id">⋯</button>
          <div :class="['menu', { open: openMenuId === v.id }]" @mouseleave="openMenuId = null">
            <div class="menu-item" @click="emit('rename')">重命名</div>
            <div class="menu-item" @click="ElMessage.info('POC 未内置「默认音色」设置，可在角色绑定里指定')">设为默认</div>
            <div class="menu-item" @click="emit('preview')">下载样本</div>
            <div class="menu-divider"></div>
            <div class="menu-item danger" @click="emit('remove')">删除</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 波形：按音色 id 做 seed，保证重渲染不跳 -->
    <div class="voice-wave">
      <i v-for="(h, i) in wave" :key="i" :style="{ height: h + '%' }"></i>
    </div>

    <!-- 标签：点 × 移除，点「+ 标签」由父组件打开标签管理 -->
    <div class="row wrap gap-2">
      <span v-for="t in v.tags" :key="t" class="chip">
        <i class="cdot" :style="{ background: tagColor(t) }"></i>{{ t }}
        <span class="x" @click="emit('removeTag', t)">×</span>
      </span>
      <span class="chip add" @click="emit('manageTags')">+ 标签</span>
    </div>

    <!-- 自定义试听：任意文本用该音色朗读 -->
    <div class="input-group mt-2">
      <input v-model="text" class="input" style="padding:8px 11px;font-size:13px" placeholder="自定义试听文本…" />
      <el-button class="btn btn-sm" @click="emit('preview')">▶ 试听</el-button>
    </div>

    <!-- 参数微调（仅本地预览用，不写库） -->
    <div class="mt-2">
      <div class="param-row">
        <span class="pname">语速</span>
        <input v-model.number="rate" type="range" class="slider" min="0.5" max="2" step="0.05" />
        <span class="pval">{{ rate.toFixed(2) }}</span>
      </div>
      <div class="param-row">
        <span class="pname">音调</span>
        <input v-model.number="pitch" type="range" class="slider" min="-12" max="12" step="1" />
        <span class="pval">{{ pitch }}st</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { Voice } from '@/types'

/**
 * 音色卡（design/voice-library.html 的 .voice-card）。
 *
 * 只负责「一张卡」的展示与本地交互：
 * - 语速 / 音调 / 试听文本都是卡内本地状态，滑动不影响数据源，也不写库；
 * - 所有会改数据的动作（勾选、改标签、试听、重命名、删除）一律 emit 给父组件，
 *   让音色库保留统一的加载与失败处理，避免每张卡各写一遍请求。
 */

const props = defineProps<{
  v: Voice
  selected: boolean
  /** 标签配色表：由父组件传入，卡内只查色不请求 */
  tagColors: Record<string, string>
}>()

const emit = defineEmits<{
  select: []
  removeTag: [tag: string]
  manageTags: []
  preview: []
  rename: []
  remove: []
}>()

/** 试听文本：留空时父组件会用默认例句，这里只是给滑杆一个可写容器 */
const text = ref('')
const rate = ref(1)
const pitch = ref(0)
/** 当前展开「⋯」菜单的音色 id */
const openMenuId = ref<number | null>(null)

/** 头像配色：按 id 稳定取色，刷新不会跳色 */
const avatarColor = computed(() => {
  const palette = ['#38bdf8', '#6366f1', '#22d3ee', '#fbbf24', '#fb7185', '#34d399']
  return palette[props.v.id % palette.length]
})

const typeText = computed(() => (props.v.type === 'clone' ? '克隆' : '内置'))

/** 状态徽标配色：克隆就绪用 ok（绿），内置就绪用 acc（蓝） */
const tone = computed(() => {
  const v = props.v
  if (v.status === 'ready') return v.type === 'clone' ? 'ok' : 'acc'
  if (v.status === 'processing' || v.status === 'training' || v.status === 'failed') return 'warn'
  return ''
})

/** 状态文案：同一状态对不同来源用词不同（克隆说「已就绪」，内置说「可用」） */
const statusText = computed(() => {
  const s = props.v.status
  if (s === 'ready') return props.v.type === 'clone' ? '已就绪' : '可用'
  if (s === 'processing') return '处理中'
  if (s === 'training') return '训练中'
  if (s === 'failed') return '失败'
  return s
})

/** 查标签配色，没定义过就回退灰 */
function tagColor(value: string) {
  return props.tagColors[value] || '#94a3b8'
}

/** 确定性波形（52 根柱），种子取自音色 id */
const wave = computed(() => {
  const seed = 1 + (props.v.id % 7) * 0.3
  return Array.from({ length: 52 }, (_, i) =>
    Math.round(16 + Math.abs(Math.sin(i * 0.5 * seed) * 0.75 + Math.sin(i * 0.17) * 0.25) * 70),
  )
})
</script>
