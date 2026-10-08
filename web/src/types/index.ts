// 与后端 Pydantic schema 对齐（docs/接口文档.md / 设计文档 §6 / DESIGN_SPEC）
// 说明：v0.3「作品工作空间」相关类型集中在下方，字段名与后端返回保持一致。

export interface User {
  id: number
  email: string
  nickname: string
  realname_verified: boolean
  voiceprint_checked: boolean
  role: string
}

// ------------------------------------------------------------------ 作品

/** Dashboard 卡片上的「工作空间摘要」三指标（DESIGN_SPEC §7b.1） */
export interface WorkSummary {
  /** 整体完成度 0~100，喂给卡片进度条与作品头环形进度 */
  progress: number
  /** 已绑定音色的角色数 */
  bound_roles: number
  /** 角色总数 */
  total_roles: number
  /** 已配音时长（分钟） */
  audio_minutes: number
}

export interface Work {
  id: number
  owner_id: number
  name: string
  author: string
  /** 作品简介（后端 WorkOut.intro） */
  intro?: string
  type: string
  lang: string
  cover_url?: string
  status: WorkStatus
  chapter_count: number
  updated_at: string | null
  /** 仅列表接口返回，详情页不带 */
  summary?: WorkSummary
}

/** 作品状态机（docs/接口文档.md §16.1） */
export type WorkStatus =
  | 'draft'
  | 'text_uploaded'
  | 'parsing'
  | 'pending_review'
  | 'review_done'
  | 'synthesizing'
  | 'synth_done'
  | 'exporting'
  | 'completed'
  | 'archived'
  | 'deleted'

// ------------------------------------------------------- 制作进度流水线

/** 流水线某一段的人工介入动作（DESIGN_SPEC §5.3b） */
export interface StageAction {
  key: string
  label: string
}

/** 六段流水线的一段：上传 / 解析 / 人工校对 / 声纹绑定 / 合成配音 / 导出 */
export interface PipelineStage {
  key: 'upload' | 'parse' | 'proofread' | 'cast' | 'synth' | 'export'
  label: string
  /** done / active / idle，前端映射 .pipe-stage 三种配色 */
  status: 'done' | 'active' | 'idle' | 'error'
  index: number
  /** 该段耗时（秒） */
  seconds: number
  progress: number
  actions: StageAction[]
}

/** 解析内容汇总六项指标之一（前端 .metrics 六连卡） */
export interface Metric {
  key: string
  label: string
  value: number | string
  unit: string
  /** hl=主题蓝 / ok=绿 / warn=橙 / danger=红 */
  tone: 'hl' | 'ok' | 'warn' | 'danger'
}

// ------------------------------------------------------------ 角色与绑定

export interface Role {
  id: number
  name: string
  /** main=主角 / supporting=配角 / extra=龙套 */
  level: string
  aliases: string[]
  profile?: Record<string, any>
  /** 台词条数 */
  line_count: number
  bound_voice_id?: number | null
  bound_voice_name?: string | null
  params?: Record<string, unknown>
  bound?: boolean
}

export interface Binding {
  role_id: number
  role_name?: string
  voice_id: number | null
  voice_name?: string | null
  params?: Record<string, unknown>
  bound?: boolean
}

/** 克隆合规前置（DESIGN_SPEC §7b.2） */
export interface CloneCompliance {
  realname_verified: boolean
  voiceprint_checked: boolean
  banned_keywords_hit: boolean
  watermark_enabled: boolean
}

// ---------------------------------------------------------------- 片段

export type SegmentType = 'narration' | 'dialogue' | 'psychology'

export interface Segment {
  id: number
  chapter_id: number
  order: number
  type: SegmentType
  text: string
  speaker_role_id: number | null
  speaker_name: string | null
  emotion: string
  intensity: number
  confidence: number
  low_conf: boolean
}

/** 片段行可人工修改的字段（后端 PATCHABLE_FIELDS 白名单） */
export interface SegmentPatch {
  type?: SegmentType
  text?: string
  speaker_role_id?: number
  speaker_name?: string
  emotion?: string
  intensity?: number
  confidence?: number
}

// ---------------------------------------------------------- 人物关系图

/** 关系图节点（=角色） */
export interface GraphNode {
  id: number
  name: string
  level: string
  aliases: string[]
  line_count: number
  /** 配色提示，来自角色画像 profile.color */
  color_hint?: string
}

/** 关系图连线（=角色关系） */
export interface GraphEdge {
  id: number
  from: number
  to: number
  label: string
  /** narration=旁白叙述 / kinship=亲属 / mate=同伴 / other=其他 */
  kind: 'narration' | 'kinship' | 'mate' | 'other'
  /** 0~1，前端映射连线线宽 */
  weight: number
  /** auto=待确认（虚线）/ manual=已确认（实线强关系） */
  source: 'auto' | 'manual'
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ------------------------------------------------------------ 音频与导出

/** 音频资产种类：样章 / 分章 / 分角色轨 / 全本 */
export type AssetKind = 'sample' | 'chapter' | 'role_track' | 'full'

export interface AudioAsset {
  id: number
  kind: AssetKind
  chapter_id: number | null
  role_id: number | null
  url: string
  duration: number
  size: number
  status: 'ready' | 'processing' | 'failed'
  created_at: string
}

export interface ExportRecord {
  id: number
  format: string
  url: string
  duration: number
  params: Record<string, unknown>
  expires_at: string | null
  created_at: string
}

// ------------------------------------------------------ 人工修改留痕

/** 一条修改留痕（前端渲染 <del> 红 / <ins> 绿 的前后 diff） */
export interface EditLog {
  id: number
  object_type: 'role' | 'binding' | 'segment' | 'relation' | 'work'
  object_id: number | null
  field: string
  old_value: string | null
  new_value: string | null
  /** update=人工改 / revert=回滚 / auto=重跑覆盖 */
  action: 'update' | 'revert' | 'auto'
  note: string | null
  created_at: string
}

/** 版本快照胶囊（v1…vN） */
export interface Snapshot {
  id: number
  version: number
  label: string
  created_at: string
}

// ------------------------------------------------------------ 音色相关

export interface Voice {
  id: number
  name: string
  type: 'builtin' | 'clone'
  engine: string
  tags: string[]
  status: string
  usage_count?: number
  owner_id?: number | null
}

export interface VoiceTag {
  id: number
  dim: string
  value: string
  group: string | null
  scope: 'global' | 'work'
  color: string | null
  usage_count: number
}

// -------------------------------------------------------- 工作空间全景

export interface ChapterNode {
  id: number
  title: string
  order: number
  segment_count: number
  low_conf_count: number
  /** done=已解析 / empty=空章，前端映射 .chap-node 三态点 */
  status: 'done' | 'empty'
}

export interface CastOverview {
  roles: Role[]
  bindings: Binding[]
  compliance: CloneCompliance
}

/** GET /works/{id}/overview 的完整返回（工作空间首屏） */
export interface OverviewData {
  work: {
    id: number
    name: string
    author: string
    type: string
    lang: string
    cover_url: string
    status: WorkStatus
    progress: number
  }
  pipeline: PipelineStage[]
  metrics: Metric[]
  cast: CastOverview
  graph: GraphData
  chapters: ChapterNode[]
  assets: AudioAsset[]
  edits: EditLog[]
  snapshots: Snapshot[]
}

// ---------------------------------------------------------------- 任务

export interface Task {
  id: string
  work_id: number | null
  type: 'parse' | 'synth' | 'clone'
  status: string
  progress: number
  stage: string
  result_ref: string | null
  subtitle_ref: string | null
}

export interface SynthStatus {
  task_id: string
  status: string
  progress: number
  audio_url: string | null
  subtitle_url: string | null
  failed_segments: number
}
