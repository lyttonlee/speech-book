<template>
<!--FRAG:overview-->
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import * as rolesApi from '@/api/roles'
import { RELATION_KIND_COLOR } from '@/utils/status'
import { fmtTime } from '@/utils/format'
import type { GraphEdge, Role } from '@/types'

/**
 * 解析内容汇总（design/workspace.html §4）。
 *
 * 六连指标 + 角色总览 + 声纹绑定总览 + 关系图缩略，全是只读视图，
 * 除了「新增角色」和「立即绑定」两个入口，其它都不改数据。
 */

const props = defineProps<{ workId: number }>()
const emit = defineEmits<{ go: [id: string] }>()

const store = useWorkStore()

// ---------------------------------------------------------------- 指标派生
const boundCount = computed(() => store.roles.filter((r) => r.bound).length)
/** 绑定完成率 0~1（声纹绑定总览的第二个环） */
const bindRatio = computed(() => (store.roles.length ? boundCount.value / store.roles.length : 0))
const pendingEdges = computed(() => store.graph.edges.filter((e) => e.source === 'auto').length)
const lastEditAt = computed(() => (store.edits[0] ? fmtTime(store.edits[0].created_at) : ''))

/** 关系图：中心度最高的角色（按度数排序取第一） */
const topRoleName = computed(() => {
  const deg = new Map<number, number>()
  for (const e of store.graph.edges) {
    deg.set(e.from, (deg.get(e.from) ?? 0) + 1)
    deg.set(e.to, (deg.get(e.to) ?? 0) + 1)
  }
  let best: GraphEdge['from'] | null = null
  let bestDeg = -1
  for (const [id, d] of deg) if (d > bestDeg) { bestDeg = d; best = id }
  return store.graph.nodes.find((n) => n.id === best)?.name ?? '—'
})

/** 悬空节点：没有任何连线的角色 */
const orphanCount = computed(() => {
  const linked = new Set<number>()
  for (const e of store.graph.edges) { linked.add(e.from); linked.add(e.to) }
  return store.graph.nodes.filter((n) => !linked.has(n.id)).length
})

// ---------------------------------------------------------------- 角色卡
/** 角色取色：优先画像里的 color，否则按索引取稳定色板（避免刷新跳色） */
function roleColor(r: Role, index: number): string {
  const palette = ['#38bdf8', '#6366f1', '#22d3ee', '#fbbf24', '#fb7185', '#34d399']
  return (r.profile?.color as string) || palette[index % palette.length]
}

function levelText(level: string): string {
  return { main: '主角', supporting: '配角', extra: '龙套' }[level] ?? level
}

/** 角色卡上的标签：画像里的性别 / 音色适配 / 性格，最多 3 个 */
function roleTags(r: Role): string[] {
  const p = (r.profile ?? {}) as Record<string, unknown>
  const out: string[] = []
  for (const k of ['gender', 'age', 'tone', 'personality']) {
    const v = p[k]
    if (typeof v === 'string' && v) out.push(v)
  }
  return out.slice(0, 3)
}

/** 角色置信度：取画像 confidence，缺失返回 null（不展示进度条） */
function roleConf(roleId: number): number | null {
  const c = store.roles.find((x) => x.id === roleId)?.profile?.confidence
  return typeof c === 'number' ? c : null
}

function isRoleAdjusted(roleId: number): boolean {
  return store.edits.some((e) => e.object_type === 'role' && e.object_id === roleId)
}

function selectRole(roleId: number) {
  store.selectRole(store.selectedRoleId === roleId ? null : roleId)
}

/** 「立即绑定」：跳到角色与声纹绑定区块并选中该角色 */
function bindRole(roleId: number) {
  store.selectRole(roleId)
  emit('go', 'cast')
}

// ---------------------------------------------------------------- 关系图缩略
/** 缩略图布局：与 RelationGraph 的 pos() 同一套规则，只是画布更小 */
function miniPos(index: number): { x: number; y: number } {
  const W = 420, H = 250, cx = W / 2, cy = H / 2
  const list = store.graph.nodes
  const centerIdx = list.findIndex((n) => n.id === 0)
  if (index === centerIdx) return { x: cx, y: cy }
  const rest = list.filter((n) => n.id !== 0)
  const restIndex = index > centerIdx && centerIdx >= 0 ? index - 1 : index
  const n = Math.max(1, rest.length)
  const a = -Math.PI / 2 + (restIndex * 2 * Math.PI) / n
  return { x: cx + 96 * Math.cos(a), y: cy + 80 * Math.sin(a) }
}

/** 缩略图连线：二次贝塞尔，法线偏移 12% 避免重叠 */
function miniEdgePath(e: GraphEdge): string {
  const ai = store.graph.nodes.findIndex((n) => n.id === e.from)
  const bi = store.graph.nodes.findIndex((n) => n.id === e.to)
  const a = miniPos(ai), b = miniPos(bi)
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
  const dx = b.x - a.x, dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const k = 0.12 * len
  return `M ${a.x} ${a.y} Q ${mx + (-dy / len) * k} ${my + (dx / len) * k} ${b.x} ${b.y}`
}

function kindColor(kind: string): string {
  return RELATION_KIND_COLOR[kind] ?? RELATION_KIND_COLOR.other
}

// ---------------------------------------------------------------- 动作
/** 六连卡的补充说明文案（key 与后端指标口径对齐） */
const METRIC_SUB: Record<string, string> = {
  chapter_count: '已解析章节总数',
  segment_count: '对话 / 叙述 / 心理',
  role_count: '含旁白',
  bound_count: '未绑走默认旁白',
  audio_seconds: '全部音频资产',
  low_conf: '说话人待人工确认',
}
function metricSub(key: string): string {
  return METRIC_SUB[key] ?? ''
}

/** 新增角色：角色卡里的虚线卡，名字弹窗输入 */
async function createRole() {
  try {
    const { value } = await ElMessageBox.prompt('新角色名', '新增角色', {
      confirmButtonText: '创建', cancelButtonText: '取消',
    })
    if (!value) return
    await rolesApi.createRole(props.workId, value, 'supporting')
    await store.loadOverview(props.workId)
    ElMessage.success('角色已创建')
  } catch {
    /* 用户取消 */
  }
}

/** 导出解析报告：overview 原始数据直接落 JSON */
function exportReport() {
  const blob = new Blob([JSON.stringify({
    work: store.currentWork,
    metrics: store.metrics,
    cast: { roles: store.roles, bindings: store.bindings },
    graph: store.graph,
    chapters: store.chapters,
  }, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${store.currentWork?.name ?? 'work'}-report.json`
  a.click()
  URL.revokeObjectURL(url)
}
</script>
