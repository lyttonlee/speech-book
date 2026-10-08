<template>
  <!-- ==================== 6. 人物关系图（可编辑） ==================== -->
  <section class="section anchor" id="graph">
    <div class="sec-head">
      <div>
        <h2>人物关系图</h2>
        <div class="desc">节点 = 角色，连线 = 关系（粗细=强度，虚线=人工待确认）。点节点看画像，改关系即时留痕。</div>
      </div>
      <el-button class="btn btn-sm sec-fold" @click="exportGraph">导出图谱</el-button>
    </div>

    <RelationGraph
      :work-id="workId"
      :data="store.graph"
      @upsert="onUpsertEdge"
      @delete="onDeleteEdge"
      @derive="onDeriveGraph"
    />
    <p class="hint">
      关系抽取为 M2 能力；人工确认过的边标记为实线（source=manual），
      参与后续「重点角色优先分配音色」的推荐排序。
    </p>
  </section>
</template>

<script setup lang="ts">
/**
 * 人物关系图区块（design/workspace.html §6）。
 *
 * 整块只是一个「关系图 + 导出」的壳：画图、点选、编辑关系都交给 RelationGraph 子组件，
 * 本组件把子组件抛出的三个事件（新增/修改边、删除边、重新推导）接到 store 上，
 * 避免把画布逻辑塞进工作空间主页面。
 */

import { useWorkStore } from '@/stores/work'
import RelationGraph from './RelationGraph.vue'

const props = defineProps<{ workId: number }>()

const store = useWorkStore()

/** 新增或改一条关系：由 store 落库，成功后刷新全景（指标里的「关系数」要跟着变） */
async function onUpsertEdge(payload: Parameters<typeof store.upsertEdge>[1]) {
  await store.upsertEdge(props.workId, payload)
}

/** 删除一条关系 */
async function onDeleteEdge(relationId: number) {
  await store.deleteEdge(props.workId, relationId)
}

/** 重新推导：调后端的关系抽取（M2 能力，POC 是启发式） */
async function onDeriveGraph() {
  await store.deriveGraph(props.workId)
}

/** 导出图谱为 JSON 文件下载 */
function exportGraph() {
  const blob = new Blob([JSON.stringify(store.graph, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${store.currentWork?.name ?? 'work'}-graph.json`
  a.click()
  URL.revokeObjectURL(url)
}
</script>
