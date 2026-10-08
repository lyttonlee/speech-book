import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as worksApi from '@/api/works'
import * as proofreadApi from '@/api/proofread'
import * as graphApi from '@/api/graph'
import * as auditApi from '@/api/audit'
import * as bindingsApi from '@/api/bindings'
import type {
  AudioAsset, Binding, ChapterNode, CloneCompliance, EditLog, GraphData, GraphNode,
  Metric, OverviewData, PipelineStage, Role, Segment, SegmentPatch, Snapshot, Voice, Work,
} from '@/types'

/**
 * 工作空间 store（单本书的全部状态）。
 *
 * 设计要点（DESIGN_SPEC §5.3b）：
 * - 首屏只发一次 `loadOverview`（服务端聚合接口），后续局部刷新用专门的接口；
 * - 所有人工改动都走 `withSaving`，让 UI 有「保存中 → 已保存」的即时反馈；
 * - 改动后只刷新受影响的分片，不做整页重载。
 */
export const useWorkStore = defineStore('work', () => {
  // ---------------------------------------------------------- 基础状态
  const works = ref<Work[]>([])
  const currentWork = ref<Work | null>(null)

  // ---------------------------------------------------- 工作空间全景数据
  const pipeline = ref<PipelineStage[]>([])
  const metrics = ref<Metric[]>([])
  const roles = ref<Role[]>([])
  /** 音色库（Studio 四步向导的角色绑定步骤要用，工作空间页走 CastBinding 自行拉取） */
  const voices = ref<Voice[]>([])
  /** 当前展示的片段列表（Studio 解析完成后落到这里，供向导后续步骤使用） */
  const segments = ref<Segment[]>([])
  const bindings = ref<Binding[]>([])
  const graph = ref<GraphData>({ nodes: [], edges: [] })
  const chapters = ref<ChapterNode[]>([])
  const assets = ref<AudioAsset[]>([])
  const edits = ref<EditLog[]>([])
  const snapshots = ref<Snapshot[]>([])
  const compliance = ref<CloneCompliance>({
    realname_verified: false,
    voiceprint_checked: false,
    banned_keywords_hit: false,
    watermark_enabled: true,
  })

  // ------------------------------------------------------------ 交互状态
  const loading = ref(false)
  /** 正在保存的动作键（格式 `对象类型:id:字段`），用于行内 loading 态 */
  const savingKeys = ref<string[]>([])
  /** 吸顶子导航当前高亮锚点 */
  const activeAnchor = ref('overview')
  /** 关系图 / 角色卡当前选中的角色 id */
  const selectedRoleId = ref<number | null>(null)

  // -------------------------------------------------------------- 派生值
  /** 未绑定音色的角色（「一键补绑」入口要用） */
  const unboundRoles = computed(() => roles.value.filter((r) => !r.bound))

  /** 待人工处理数量：低置信片段 + 未绑定角色，喂给顶部警示条 .notice */
  const pendingCount = computed(() => {
    const low = chapters.value.reduce((sum, c) => sum + c.low_conf_count, 0)
    return low + unboundRoles.value.length
  })

  /** 当前选中的角色节点（关系图详情面板用） */
  const selectedRole = computed<GraphNode | null>(
    () => graph.value.nodes.find((n) => n.id === selectedRoleId.value) ?? null,
  )

  // -------------------------------------------------------------- 工具函数

  /**
   * 统一的保存包装器：给保存动作加「保存中 → 已保存」反馈。
   * @param key 这次保存的唯一键，通常是 `对象类型:id:字段`
   * @param fn  真正执行的请求
   */
  async function withSaving<T>(key: string, fn: () => Promise<T>): Promise<T> {
    savingKeys.value.push(key)
    try {
      return await fn()
    } finally {
      savingKeys.value = savingKeys.value.filter((k) => k !== key)
    }
  }

  /** 判断是否正在保存某个键（供 :class 绑定 loading 态） */
  function isSaving(key: string) {
    return savingKeys.value.includes(key)
  }

  // ------------------------------------------------------------ 数据加载

  /** 加载作品列表（Dashboard） */
  async function loadWorks(params?: Parameters<typeof worksApi.listWorks>[0]) {
    loading.value = true
    try {
      const res = await worksApi.listWorks(params)
      works.value = res.items ?? []
      return res
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载工作空间全景（首屏唯一主请求）。
   * 一次拿回：作品头 / 流水线 / 指标 / 角色与绑定 / 关系图 / 章节树 / 资产 / 留痕 / 快照。
   */
  async function loadOverview(workId: number) {
    loading.value = true
    try {
      const data = await worksApi.getOverview(workId)
      applyOverview(data)
      return data
    } finally {
      loading.value = false
    }
  }

  /** 把全景数据铺到各个响应式分片上 */
  function applyOverview(data: OverviewData) {
    const prev = currentWork.value
    currentWork.value = {
      id: data.work.id,
      name: data.work.name,
      author: data.work.author,
      type: data.work.type,
      lang: data.work.lang,
      cover_url: data.work.cover_url,
      status: data.work.status,
      chapter_count: data.chapters.length,
      owner_id: prev?.owner_id ?? 0,
      updated_at: prev?.updated_at ?? null,
      summary: {
        progress: data.work.progress,
        bound_roles: data.cast.roles.filter((r) => r.bound).length,
        total_roles: data.cast.roles.length,
        audio_minutes: data.assets.reduce((s, a) => s + a.duration, 0) / 60,
      },
    }
    pipeline.value = data.pipeline
    metrics.value = data.metrics
    roles.value = data.cast.roles
    bindings.value = data.cast.bindings
    compliance.value = data.cast.compliance
    graph.value = data.graph
    chapters.value = data.chapters
    assets.value = data.assets
    edits.value = data.edits
    snapshots.value = data.snapshots
  }

  /** 只刷新流水线（解析/合成进行时轮询用，比 overview 轻） */
  async function refreshPipeline(workId: number) {
    pipeline.value = (await worksApi.getPipeline(workId)).items ?? []
  }

  async function refreshAssets(workId: number) {
    assets.value = (await worksApi.listAssets(workId)).items ?? []
  }

  async function refreshEdits(workId: number) {
    edits.value = (await auditApi.listEdits(workId)).items ?? []
  }

  async function refreshGraph(workId: number) {
    graph.value = await graphApi.getGraph(workId)
  }

  // ------------------------------------------------------- 人工调整动作

  /** 改片段字段（类型/说话人/情绪/强度/正文），改完自动刷新留痕与全景指标 */
  async function patchSegment(workId: number, segmentId: number, patch: SegmentPatch) {
    const key = `segment:${segmentId}:${Object.keys(patch).join(',')}`
    return withSaving(key, async () => {
      const res = await proofreadApi.patchSegment(workId, segmentId, patch)
      await loadOverview(workId)
      return res
    })
  }

  /** 把片段还原为 AI 原值 */
  async function revertSegment(workId: number, segmentId: number, field = 'all') {
    return withSaving(`segment:${segmentId}:revert`, async () => {
      const res = await proofreadApi.revertSegment(workId, segmentId, field)
      await loadOverview(workId)
      return res
    })
  }

  /** 批量改片段 */
  async function batchPatchSegments(workId: number, ids: number[], patch: SegmentPatch) {
    return withSaving('segment:batch', async () => {
      const res = await proofreadApi.batchPatchSegments(workId, ids, patch)
      await loadOverview(workId)
      return res
    })
  }

  /** 设置角色-音色绑定（role_id=0 表示旁白） */
  async function setBindings(workId: number, items: Binding[]) {
    return withSaving('binding:all', async () => {
      const res = await bindingsApi.setBindings(workId, items)
      await loadOverview(workId)
      return res
    })
  }

  /** 自动绑定（按音色标签匹配） */
  async function autoBind(workId: number) {
    return withSaving('binding:auto', async () => {
      const res = await bindingsApi.autoBind(workId)
      await loadOverview(workId)
      return res
    })
  }

  /** 新增/修改关系边 */
  async function upsertEdge(workId: number, payload: Parameters<typeof graphApi.upsertEdge>[1]) {
    return withSaving('graph:upsert', async () => {
      const res = await graphApi.upsertEdge(workId, payload)
      await refreshGraph(workId)
      return res
    })
  }

  /** 删除关系边（破坏性操作，调用方负责二次确认） */
  async function deleteEdge(workId: number, relationId: number) {
    return withSaving(`graph:${relationId}`, async () => {
      const res = await graphApi.deleteEdge(workId, relationId)
      await refreshGraph(workId)
      return res
    })
  }

  /** 一键恢复自动推导的关系边 */
  async function deriveGraph(workId: number) {
    return withSaving('graph:derive', async () => {
      const res = await graphApi.deriveGraph(workId)
      await refreshGraph(workId)
      return res
    })
  }

  /** 逐条回滚某条修改留痕 */
  async function rollbackEdit(workId: number, logId: number) {
    return withSaving(`edit:${logId}`, async () => {
      const res = await auditApi.rollbackEdit(workId, logId)
      await loadOverview(workId)
      return res
    })
  }

  /** 整体回滚到版本快照 */
  async function restoreSnapshot(workId: number, snapshotId: number) {
    return withSaving(`snapshot:${snapshotId}`, async () => {
      const res = await auditApi.restoreSnapshot(workId, snapshotId)
      await loadOverview(workId)
      return res
    })
  }

  /** 保存版本快照 */
  async function createSnapshot(workId: number, label: string) {
    return withSaving('snapshot:new', async () => {
      const res = await auditApi.createSnapshot(workId, label)
      await loadOverview(workId)
      return res
    })
  }

  /** 选中角色（联动角色卡与关系图详情面板） */
  function selectRole(roleId: number | null) {
    selectedRoleId.value = roleId
  }

  /** 切换锚点（吸顶子导航滚动高亮用） */
  function setAnchor(anchor: string) {
    activeAnchor.value = anchor
  }

  // -------------------------------------------- 局部写入（Studio 向导用）
  // 说明：这些是「非全景接口」的局部回填入口。解析完成后把角色 / 片段 / 音色
  // 直接写进 store，避免向导后续步骤再各发一次请求。

  /** 写入当前作品（新建 / 打开某本书时调用） */
  function setWork(w: Work) {
    currentWork.value = w
  }

  /** 写入音色列表 */
  function setVoices(list: Voice[]) {
    voices.value = list
  }

  /** 写入片段列表 */
  function setSegments(list: Segment[]) {
    segments.value = list
  }

  /** 写入角色列表 */
  function setRoles(list: Role[]) {
    roles.value = list
  }

  function reset() {
    currentWork.value = null
    pipeline.value = []
    metrics.value = []
    roles.value = []
    voices.value = []
    segments.value = []
    bindings.value = []
    graph.value = { nodes: [], edges: [] }
    chapters.value = []
    assets.value = []
    edits.value = []
    snapshots.value = []
    selectedRoleId.value = null
  }

  return {
    // state
    works, currentWork, pipeline, metrics, roles, voices, segments, bindings, graph, chapters,
    assets, edits, snapshots, compliance, loading, savingKeys, activeAnchor, selectedRoleId,
    // getters
    unboundRoles, pendingCount, selectedRole,
    // actions
    withSaving, isSaving, loadWorks, loadOverview, applyOverview,
    refreshPipeline, refreshAssets, refreshEdits, refreshGraph,
    patchSegment, revertSegment, batchPatchSegments,
    setBindings, autoBind, upsertEdge, deleteEdge, deriveGraph,
    rollbackEdit, restoreSnapshot, createSnapshot,
    setWork, setVoices, setSegments, setRoles, selectRole, setAnchor, reset,
  }
})
