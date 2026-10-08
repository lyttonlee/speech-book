import http from './request'
import type { GraphData, GraphEdge } from '@/types'

/**
 * 人物关系图接口（workspace.html `#graph` 区块）。
 * 设计约束：节点=角色，连线=关系；线宽=weight，虚线=source=auto（待确认）。
 */

/** 整张图：nodes + edges */
export function getGraph(workId: number) {
  return http.get<GraphData>(`/works/${workId}/graph`)
}

/** 从角色共现自动推导关系边（source=auto，前端显示虚线） */
export function deriveGraph(workId: number) {
  return http.post<{ derived: number; total: number }>(`/works/${workId}/graph/derive`)
}

/**
 * 新增或修改一条关系边。
 * 改过的边后端会把 source 抬到 manual，前端从虚线变实线（强关系）。
 */
export function upsertEdge(workId: number, payload: {
  id?: number
  from_role_id: number
  to_role_id: number
  label?: string
  kind?: GraphEdge['kind']
  weight?: number
}) {
  return http.put<GraphEdge>(`/works/${workId}/graph`, payload)
}

/** 删除一条关系边（破坏性操作，前端需二次确认） */
export function deleteEdge(workId: number, relationId: number) {
  return http.delete(`/works/${workId}/graph/${relationId}`)
}
