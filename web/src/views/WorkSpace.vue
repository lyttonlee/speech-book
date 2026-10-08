<template>
  <div class="ws">
    <!-- 全局渐变定义：design.css 的 .ring .r-fg 用 url(#ringGrad) 描边，
         渐变按 id 全文档查找，必须挂在文档里，故单独放一个 0 尺寸 svg -->
    <svg width="0" height="0" style="position:absolute" aria-hidden="true">
      <defs>
        <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#38bdf8" />
          <stop offset="100%" stop-color="#6366f1" />
        </linearGradient>
      </defs>
    </svg>

    <!-- 加载态 -->
    <div v-if="store.loading && !work" class="panel" style="padding:60px;text-align:center;color:var(--text-3)">
      正在载入工作空间…
    </div>

    <template v-else-if="work">
      <!-- ① 作品头 + ② 六段流水线 -->
      <div class="panel mb">
        <WorkHero @go="scrollTo" @archive="archiveWork" />
        <PipelineBar
          :work-id="workId"
          @go="scrollTo"
          @rerun="rerunParse"
          @synth="startSynth('full')"
        />
      </div>

      <!-- ③ 吸顶子导航（滚动高亮见 onScroll） -->
      <nav class="subnav ws-subnav">
        <a
          v-for="a in navItems" :key="a.id"
          :class="['sub-link', { active: store.activeAnchor === a.id }]"
          href="javascript:;"
          @click="scrollTo(a.id)"
        >
          {{ a.label }}<span v-if="a.count" class="cnt">{{ a.count }}</span>
        </a>
        <a class="sub-link right" href="javascript:;" @click="refreshAll">↻ 同步状态</a>
      </nav>

      <!-- ④ 解析内容汇总 -->
      <ParseOverview :work-id="workId" @go="scrollTo" />

      <!-- ⑤ 角色与声纹绑定 -->
      <CastPanel :work-id="workId" @go="scrollTo" />

      <!-- ⑥ 人物关系图（可编辑） -->
      <GraphPanel :work-id="workId" />

      <!-- ⑦ 已解析章节（三栏校对台） -->
      <ProofreadPanel ref="proofreadRef" :work-id="workId" @synth="startSynth('full')" />

      <!-- ⑧ 已制作配音 -->
      <AudioPanel :work-id="workId" />

      <!-- ⑨ 人工修改留痕与版本快照 -->
      <AuditPanel :work-id="workId" />

      <!-- ⑩ 导出成品 -->
      <ExportPanel :work-id="workId" />
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * 单书工作空间（design/workspace.html 的 Vue 实现，DESIGN_SPEC §5.3b）。
 *
 * 本组件只做「编排」：
 *   - 首屏一次 `overview` 拉全景，之后按区块局部刷新（章节片段 / 关系图 / 资产 / 留痕）；
 *   - 维护吸顶子导航的滚动高亮；
 *   - 把子导航跳区块、重新解析、归档这几个跨区块动作集中在这里，子组件只抛事件。
 *
 * 各区块的 UI 与业务逻辑都在 components/workspace/* 里，
 * 保持主页面短小，便于后续单独调整某个区块而不牵连全局。
 */

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import * as worksApi from '@/api/works'
import * as parseApi from '@/api/parse'
import * as synthApi from '@/api/synth'
import WorkHero from '@/components/workspace/WorkHero.vue'
import PipelineBar from '@/components/workspace/PipelineBar.vue'
import ParseOverview from '@/components/workspace/ParseOverview.vue'
import CastPanel from '@/components/workspace/CastPanel.vue'
import GraphPanel from '@/components/workspace/GraphPanel.vue'
import ProofreadPanel from '@/components/workspace/ProofreadPanel.vue'
import AudioPanel from '@/components/workspace/AudioPanel.vue'
import AuditPanel from '@/components/workspace/AuditPanel.vue'
import ExportPanel from '@/components/workspace/ExportPanel.vue'

const route = useRoute()
const router = useRouter()
const store = useWorkStore()

/** 路由参数里的作品 id */
const workId = computed(() => Number(route.params.id))

/** 作品（仅用于判断是否已加载） */
const work = computed(() => store.currentWork)

/** 校对台子组件实例：重新解析后要把当前章节重新拉一遍 */
const proofreadRef = ref<InstanceType<typeof ProofreadPanel> | null>(null)

// ---------------------------------------------------------------- 子导航

/** 子导航项：label + 角标计数（与设计稿一致，count 为空则不显示角标） */
const navItems = computed(() => [
  { id: 'overview', label: '总览汇总', count: '' },
  { id: 'cast', label: '角色与声纹', count: String(store.roles.length) },
  { id: 'graph', label: '关系图', count: String(store.graph.edges.length) },
  { id: 'chapters', label: '已解析章节', count: '' },
  { id: 'audio', label: '已制作配音', count: `${store.assets.length} 条` },
  { id: 'audit', label: '修改留痕', count: String(store.edits.length) },
  { id: 'export', label: '导出成品', count: '' },
])

/** 滚动到指定锚点（130px 补偿吸顶子导航，见 design.css .anchor） */
function scrollTo(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  const top = el.getBoundingClientRect().top + window.scrollY - 130
  window.scrollTo({ top, behavior: 'smooth' })
  store.setAnchor(id)
}

/**
 * 滚动监听：以视口上方 200px 为基准，找最后一个已滚过的区块作为当前锚点。
 * 用 passive 注册（onMounted 里），避免影响滚动性能。
 */
function onScroll() {
  const y = window.scrollY + 200
  let cur = 'overview'
  for (const a of navItems.value) {
    const el = document.getElementById(a.id)
    if (el && el.getBoundingClientRect().top + window.scrollY <= y) cur = a.id
  }
  store.setAnchor(cur)
}

// ---------------------------------------------------------------- 区块动作

/**
 * 重新解析（流水线「重新解析」按钮）。
 * 后端会保留人工修正（按留痕还原），所以重跑不会丢改动。
 */
async function rerunParse() {
  await parseApi.startParse(workId.value)
  await store.loadOverview(workId.value)
  // 章节明细与留痕也要跟着重刷，否则界面还停留在旧片段上
  await proofreadRef.value?.reload()
  await store.refreshEdits(workId.value)
  ElMessage.success('已重新提交解析任务')
}

/** 提交全本合成（流水线 / 校对台完成按钮都走这里） */
async function startSynth(scope: 'sample' | 'full' | 'range') {
  await synthApi.startSynth(workId.value, scope)
  ElMessage.success('合成任务已提交')
}

/**
 * 归档：POC 用「删除进回收站」实现（30 天内可 restore）。
 * 破坏性动作，先二次确认，成功后回列表页。
 */
async function archiveWork() {
  try {
    await ElMessageBox.confirm(
      '归档后作品进入回收站，30 天内可恢复。确定归档吗？',
      '归档作品',
      { type: 'warning', confirmButtonText: '归档', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await worksApi.deleteWork(workId.value)
  ElMessage.success('已归档')
  router.push('/dashboard')
}

/** 顶部「同步状态」：重拉全景 + 当前章节 + 留痕 + 资产 */
async function refreshAll() {
  await store.loadOverview(workId.value)
  // reload() 内部会「当前选中章节 + 待复核队列」一起重拉，比单独 loadChapter 更完整
  await proofreadRef.value?.reload()
  await store.refreshEdits(workId.value)
  await store.refreshAssets(workId.value)
  ElMessage.success('已同步')
}

// ---------------------------------------------------------------- 生命周期

/** 载入工作空间：全景 → 首章片段 → 待复核 */
async function load() {
  await store.loadOverview(workId.value)
  await store.refreshEdits(workId.value)
  await store.refreshAssets(workId.value)
}

onMounted(async () => {
  // 记住最近进入的作品，侧栏「继续上一本书」要用
  localStorage.setItem('sb_last_work_id', String(workId.value))
  await load()
  window.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})

// 切换书时重置局部状态（路由复用组件时会走到这里）
watch(() => route.params.id, async (id, old) => {
  if (id && id !== old) {
    await load()
  }
})
</script>

<style scoped>
/* 子导航：design.css 的 .subnav 按 .content 的 --sp-8 内边距做负 margin，
   这里补上 ws 容器的上下内边距 */
.ws-subnav {
  margin-top: 0;
  margin-bottom: var(--sp-8);
}
</style>
