// 与后端 Pydantic schema 对齐（docs/接口文档.md / 设计文档 §6）
export interface User {
  id: number
  email: string
  nickname: string
  realname_verified: boolean
  voiceprint_checked: boolean
  role: string
}

export interface Work {
  id: number
  owner_id: number
  name: string
  author: string
  type: string
  lang: string
  status: string
  chapter_count: number
  updated_at: string | null
}

export interface Role {
  id: number
  name: string
  level: string
  aliases: string[]
  line_count: number
}

export interface Voice {
  id: number
  name: string
  type: string
  engine: string
  tags: string[]
  status: string
}

export interface Binding {
  role_id: number
  voice_id: number | null
  params?: Record<string, unknown>
}

export interface Segment {
  id: number
  chapter_id: number
  order: number
  type: 'narration' | 'dialogue' | 'psychology'
  text: string
  speaker_role_id: number | null
  speaker_name: string | null
  emotion: string
  intensity: number
  confidence: number
  low_conf: boolean
}

export interface SynthStatus {
  task_id: string
  status: string
  progress: number
  audio_url: string | null
  subtitle_url: string | null
  failed_segments: number
}

export interface Task {
  id: string
  work_id: number | null
  type: string
  status: string
  progress: number
  stage: string
  result_ref: string | null
  subtitle_ref: string | null
}
