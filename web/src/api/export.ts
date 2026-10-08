import http from './request'
import type { ExportRecord } from '@/types'

/**
 * 导出接口（docs/接口文档.md §14 / workspace.html `#export` 区块）。
 * POC 阶段后端不真跑 ffmpeg，直接返回现有合成产物的下载地址与导出记录。
 */

/** 提交导出。params 含采样率/比特率/是否带字幕/字幕格式/片头片尾/BGM/响度归一/水印 */
export function startExport(workId: number, params: Record<string, unknown> = {}) {
  return http.post<{ record_id: number; url: string; expires_at: string | null }>(
    `/works/${workId}/export`, params,
  )
}

/** 导出历史 */
export function listExports(workId: number) {
  return http.get<{ items: ExportRecord[]; total: number }>(`/works/${workId}/export`)
}
