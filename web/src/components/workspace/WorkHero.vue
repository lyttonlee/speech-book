<template>
  <!-- 全局渐变定义：design.css 的 .ring .r-fg 用 url(#ringGrad) 描边，
       SVG 引用按 id 全文档查找，所以渐变必须和 .ring 在同一个文档里 -->
  <svg width="0" height="0" style="position: absolute" aria-hidden="true">
    <defs>
      <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#38bdf8" />
        <stop offset="100%" stop-color="#6366f1" />
      </linearGradient>
    </defs>
  </svg>

<!--FRAG:hero-->
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWorkStore } from '@/stores/work'
import { statusBadgeClass, statusMeta } from '@/utils/status'

/**
 * 作品头（design/workspace.html §1）。
 *
 * 只负责「这本书现在怎么样」：身份信息 + 状态机链路 + 整体完成度环。
 * 所有会改数据的动作（归档 / 跳区块）都往外抛事件，由父组件统一处理。
 */

const emit = defineEmits<{ go: [id: string]; archive: [] }>()

const store = useWorkStore()

/** 环形进度常量：r=38 → 周长 2πr ≈ 238.76（设计稿写死的值） */
const RING_C = 238.7

/** 状态机顺序（docs/接口文档.md §16.1），用于状态链路渲染 */
const STATUS_ORDER = [
  'draft', 'text_uploaded', 'parsing', 'pending_review', 'review_done',
  'synthesizing', 'synth_done', 'exporting', 'completed',
] as const

const work = computed(() => store.currentWork)
const progress = computed(() => work.value?.summary?.progress ?? 0)
/** 封面大字：取书名首字，POC 没有真实封面图 */
const coverMark = computed(() => (work.value?.name || '书').slice(0, 1))
const compliance = computed(() => store.compliance)

/** 环形进度偏移：完成比例越大偏移越小 */
const ringOffset = computed(() => RING_C * (1 - progress.value / 100))

/**
 * 状态链路：当前状态之前的段 done，当前段 cur。
 * 传 key 是为了让 CSS 按段染成渐变 / 灰两种色。
 */
const stateChain = computed(() => {
  const cur = STATUS_ORDER.indexOf((work.value?.status ?? 'draft') as typeof STATUS_ORDER[number])
  return STATUS_ORDER.map((key, i) => ({
    key,
    label: statusMeta(key).label,
    cls: i < cur ? 'done' : i === cur ? 'cur' : '',
  }))
})

/** 「已校对」口径：本章解析完成且无低置信片段 */
const proofedChapters = computed(
  () => store.chapters.filter((c) => c.status === 'done' && !c.low_conf_count).length,
)

const nextStageLabel = computed(() => {
  const s = store.pipeline.find((p) => p.status !== 'done')
  return s ? `${s.label} 完成` : '已全部完成'
})

/** 模板里 `work` 是 computed，这里补一层可直接访问的别名 */
function go(id: string) {
  emit('go', id)
}

function archive() {
  emit('archive')
}
</script>

<style scoped>
/* 作品头只依赖设计系统，无额外样式；这里仅放开大标题换行 */
.htitle { font-size: 20px; }
</style>
