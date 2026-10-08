<template>
  <div class="graph-wrap">
    <!-- 左：SVG 关系图 -->
    <div class="panel">
      <div class="card-h">
        <h3>人物关系图</h3>
        <span class="sub">线宽 = 关系强度 · 虚线 = 待确认（点选可改）</span>
      </div>

      <svg
        ref="svgRef"
        class="graph-svg"
        viewBox="0 0 640 420"
        @click.self="selected = null"
      >
        <!-- 连线：先画边再画节点，保证节点压在线上方 -->
        <path
          v-for="e in edges"
          :key="'e' + e.id"
          :d="edgePath(e)"
          :stroke="kindColor(e.kind)"
          :stroke-width="1 + e.weight * 4"
          :stroke-dasharray="e.source === 'auto' ? '5 5' : ''"
          :class="['g-edge', edgeClass(e)]"
          fill="none"
          @click.stop="selectEdge(e)"
        />
        <!-- 关系文案：画在连线中点 -->
        <text
          v-for="e in edges"
          :key="'l' + e.id"
          :x="edgeMid(e).x"
          :y="edgeMid(e).y"
          class="g-elabel"
          text-anchor="middle"
        >{{ e.label }}</text>

        <!-- 节点 -->
        <g
          v-for="(n, i) in nodes"
          :key="'n' + n.id"
          :class="['g-node', nodeClass(n)]"
          @click.stop="selectNode(n)"
        >
          <circle class="g-halo" :cx="pos(i).x" :cy="pos(i).y" r="30" />
          <circle
            class="g-body"
            :cx="pos(i).x"
            :cy="pos(i).y"
            r="23"
            :fill="nodeColor(n)"
          />
          <text class="g-letter" :x="pos(i).x" :y="pos(i).y + 5" text-anchor="middle">
            {{ n.name.slice(0, 1) }}
          </text>
          <text class="g-label" :x="pos(i).x" :y="pos(i).y + 42" text-anchor="middle">
            {{ n.name }}
          </text>
        </g>
      </svg>

      <div class="row gap-2" style="margin-top:10px">
        <span v-for="k in kindLegend" :key="k.key" class="tiny muted">
          <i :style="legendStyle(k.color)"></i> {{ k.label }}
        </span>
      </div>

      <div class="row gap-2 mt-2">
        <el-button class="btn btn-sm" @click="derive">↻ 恢复自动推导</el-button>
      </div>
    </div>

    <!-- 右：选中对象的编辑面板 -->
    <div class="panel">
      <div class="card-h">
        <h3>{{ selectedNode ? '角色画像' : selectedEdge ? '关系编辑' : '说明' }}</h3>
        <span class="sub">{{ selectedNode ? selectedNode.name : selectedEdge ? selectedEdge.label : '点选节点或连线' }}</span>
      </div>

      <!-- 未选中：说明 -->
      <div v-if="!selectedNode && !selectedEdge" class="tiny muted">
        关系图由解析阶段的角色共现自动推导（虚线=待确认）。你可以：
        <ul style="padding-left:18px;margin-top:6px;line-height:1.9">
          <li>点选<b>节点</b>查看画像并改标签、音色适配</li>
          <li>点选<b>连线</b>改关系类型、调强度或删除（红色按钮）</li>
          <li>改动会写入「人工修改留痕」，可逐条回滚</li>
        </ul>
      </div>

      <!-- 选中节点：画像编辑 -->
      <div v-else-if="selectedNode">
        <div class="vp-row"><span class="k">角色名</span><b>{{ selectedNode.name }}</b></div>
        <div class="vp-row"><span class="k">级别</span><span>{{ levelText(selectedNode.level) }}</span></div>
        <div class="vp-row"><span class="k">台词数</span><span>{{ selectedNode.line_count }} 段</span></div>
        <div class="vp-row"><span class="k">别名</span>
          <span v-if="selectedNode.aliases?.length">{{ selectedNode.aliases.join('、') }}</span>
          <span v-else class="muted">—</span>
        </div>
        <div class="notice warn mt-2" style="font-size:12px">
          角色合并 / 拆分 / 降为龙套走「角色与声纹绑定」区块的操作菜单。
        </div>
      </div>

      <!-- 选中边：关系编辑 -->
      <div v-else-if="selectedEdge">
        <div class="field">
          <label class="tiny muted">关系文案</label>
          <input v-model="edgeForm.label" class="input" placeholder="如：妻子 / 同事 / 师徒" />
        </div>
        <div class="field">
          <label class="tiny muted">关系类型</label>
          <select v-model="edgeForm.kind" class="select">
            <option value="narration">旁白叙述</option>
            <option value="kinship">亲属</option>
            <option value="mate">同伴</option>
            <option value="other">其他</option>
          </select>
        </div>
        <div class="field">
          <label class="tiny muted">关系强度 <b>{{ edgeForm.weight.toFixed(2) }}</b></label>
          <input v-model.number="edgeForm.weight" type="range" min="0" max="1" step="0.05" class="slider" />
        </div>
        <div class="row gap-2 mt-2">
          <el-button class="btn btn-primary btn-sm" :loading="saving" @click="saveEdge">保存</el-button>
          <el-button class="btn btn-danger btn-sm" @click="removeEdge">删除关系</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { GraphData, GraphEdge, GraphNode } from '@/types'
import { RELATION_KIND_COLOR } from '@/utils/status'

const props = defineProps<{ workId: number; data: GraphData }>()
const emit = defineEmits(['upsert', 'delete', 'derive'])

/** 当前选中的节点 / 边（互斥） */
const selected = ref<{ type: 'node'; node: GraphNode } | { type: 'edge'; edge: GraphEdge } | null>(null)

const saving = ref(false)

/** 边的编辑表单 */
const edgeForm = reactive({ label: '', kind: 'other' as GraphEdge['kind'], weight: 0.5 })

const nodes = computed(() => props.data.nodes ?? [])
const edges = computed(() => props.data.edges ?? [])

const selectedNode = computed(() => (selected.value?.type === 'node' ? selected.value.node : null))
const selectedEdge = computed(() => (selected.value?.type === 'edge' ? selected.value.edge : null))

// ------------------------------------------------------------ 布局计算

/**
 * 节点坐标（640x420 视口内）。
 * 规则：旁白居中心，其余角色沿圆周均匀分布；
 * 与 design/assets/app.js 的 `layout()` 保持一致，保证原型与 Vue 版视觉一致。
 */
function pos(index: number): { x: number; y: number } {
  const W = 640, H = 420, cx = W / 2, cy = H / 2
  const list = nodes.value
  // 旁白（id=0）固定在中心
  const centerIdx = list.findIndex((n) => n.id === 0)
  if (index === centerIdx) return { x: cx, y: cy }

  const rest = list.filter((n) => n.id !== 0)
  const restIndex = index > centerIdx && centerIdx >= 0 ? index - 1 : index
  const n = Math.max(1, rest.length)
  const r = 138
  // -π/2 起算：第一个角色落在正上方，顺时针铺开
  const a = -Math.PI / 2 + (restIndex * 2 * Math.PI) / n
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) * 0.86 }
}

/** 节点坐标的索引查找 */
function nodePos(id: number) {
  const idx = nodes.value.findIndex((n) => n.id === id)
  return idx >= 0 ? pos(idx) : { x: 320, y: 210 }
}

/** 节点 → 节点中点的二次贝塞尔曲线（控制点取垂线偏移，避免直线重叠） */
function edgePath(e: GraphEdge): string {
  const a = nodePos(e.from), b = nodePos(e.to)
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
  const dx = b.x - a.x, dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  // 垂直方向偏移 12%，让相邻节点的边互相错开
  const k = 0.12 * len
  const cxp = mx + (-dy / len) * k
  const cyp = my + (dx / len) * k
  return `M ${a.x} ${a.y} Q ${cxp} ${cyp} ${b.x} ${b.y}`
}

/** 边的中点（放关系文案） */
function edgeMid(e: GraphEdge) {
  const a = nodePos(e.from), b = nodePos(e.to)
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 - 4 }
}

// ------------------------------------------------------------ 视觉映射

/** 关系类型 → 配色 */
function kindColor(kind: string) {
  return RELATION_KIND_COLOR[kind] ?? RELATION_KIND_COLOR.other
}

/** 节点配色：优先画像里的颜色，否则按索引取默认色板 */
function nodeColor(n: GraphNode) {
  return n.color_hint || '#6366f1'
}

function levelText(level: string) {
  return { main: '主角', supporting: '配角', extra: '龙套' }[level] ?? level
}

/** 节点选中态：自身高亮，其余 dim */
function nodeClass(n: GraphNode) {
  if (selectedNode.value?.id === n.id) return 'sel'
  if (selected.value) return 'dim'
  return ''
}

/** 边高亮：与选中节点相连的边保留，其余 dim */
function edgeClass(e: GraphEdge) {
  if (selectedEdge.value?.id === e.id) return 'hl'
  if (selectedNode.value) {
    return e.from === selectedNode.value.id || e.to === selectedNode.value.id ? 'hl' : 'dim'
  }
  if (selectedEdge.value) return 'dim'
  return ''
}

const kindLegend = [
  { key: 'narration', label: '旁白叙述', color: RELATION_KIND_COLOR.narration },
  { key: 'kinship', label: '亲属', color: RELATION_KIND_COLOR.kinship },
  { key: 'mate', label: '同伴', color: RELATION_KIND_COLOR.mate },
  { key: 'other', label: '其他', color: RELATION_KIND_COLOR.other },
]

function legendStyle(color: string) {
  return {
    display: 'inline-block', width: '14px', height: '3px',
    background: color, borderRadius: '2px', marginRight: '4px', verticalAlign: 'middle',
  }
}

// ------------------------------------------------------------ 交互

function selectNode(n: GraphNode) {
  selected.value = { type: 'node', node: n }
}

function selectEdge(e: GraphEdge) {
  selected.value = { type: 'edge', edge: e }
  edgeForm.label = e.label
  edgeForm.kind = e.kind
  edgeForm.weight = e.weight
}

/** 保存边的修改（后端会把 source 抬到 manual，虚线变实线） */
async function saveEdge() {
  if (!selectedEdge.value) return
  saving.value = true
  try {
    await emit('upsert', {
      id: selectedEdge.value.id,
      from_role_id: selectedEdge.value.from,
      to_role_id: selectedEdge.value.to,
      label: edgeForm.label,
      kind: edgeForm.kind,
      weight: edgeForm.weight,
    })
    ElMessage.success('已保存 · 已记入修改日志')
  } finally {
    saving.value = false
  }
}

/** 删除边：破坏性操作，红色 + 二次确认（DESIGN_SPEC §7b.3） */
async function removeEdge() {
  if (!selectedEdge.value) return
  try {
    await ElMessageBox.confirm('删除后将无法自动恢复，确定删除这条关系吗？', '删除关系', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  await emit('delete', selectedEdge.value.id)
  selected.value = null
  ElMessage.success('已删除')
}

async function derive() {
  await emit('derive')
  ElMessage.success('已按角色共现重新推导')
}

// 数据刷新后同步选中的边（避免停留在已删除的对象上）
watch(() => props.data, (d) => {
  if (selectedEdge.value) {
    const still = d.edges.find((e) => e.id === selectedEdge.value!.id)
    if (still) selected.value = { type: 'edge', edge: still }
    else selected.value = null
  }
})
</script>

<style scoped>
.graph-wrap {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}

@media (max-width: 1080px) {
  .graph-wrap {
    grid-template-columns: 1fr;
  }
}

.graph-svg {
  width: 100%;
  height: auto;
  cursor: pointer;
}

/* 节点：选中辉光，未选中时 dim 降低干扰 */
.g-node { transition: opacity 0.18s; }
.g-node.dim { opacity: 0.35; }
.g-node.sel .g-body { filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.75)); }
.g-node text { pointer-events: none; user-select: none; }
.g-letter { font-size: 15px; font-weight: 700; fill: #fff; }
.g-label { font-size: 12px; fill: var(--text-2); }
.g-halo { fill: rgba(56, 189, 248, 0.06); }

.g-edge { cursor: pointer; opacity: 0.8; transition: opacity 0.18s; }
.g-edge:hover { opacity: 1; }
.g-edge.hl { opacity: 1; }
.g-edge.dim { opacity: 0.18; }

.g-elabel { font-size: 11px; fill: var(--text-3); pointer-events: none; }

.field { margin-bottom: 12px; }
.field label { display: block; margin-bottom: 6px; }
.vp-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.14);
  font-size: 13px;
}
.vp-row .k { color: var(--text-3); }
</style>
