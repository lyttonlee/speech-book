import http from './request'
import type { EditLog, Snapshot } from '@/types'

/**
 * 人工修改留痕与版本快照（workspace.html `#audit` 区块）。
 *
 * 两种回滚粒度：
 * - `rollbackEdit`     逐条回滚：还原一条 EditLog 描述的那一个字段；
 * - `restoreSnapshot`  整体回滚：回到某个版本胶囊对应的完整状态。
 */

/** 修改日志（含前后 diff），可按对象类型筛选 */
export function listEdits(workId: number, objectType?: EditLog['object_type']) {
  return http.get<{ items: EditLog[]; total: number }>(
    `/works/${workId}/edits`, { params: { object_type: objectType } },
  )
}

/** 版本快照列表（顶部 v1…vN 胶囊） */
export function listSnapshots(workId: number) {
  return http.get<{ items: Snapshot[]; total: number }>(`/works/${workId}/snapshots`)
}

/** 保存版本快照（payload 留空时后端自动快照角色+绑定+关系） */
export function createSnapshot(workId: number, label: string) {
  return http.post<{ id: number; version: number; label: string }>(
    `/works/${workId}/snapshots`, { label },
  )
}

/** 整体回滚到某个版本快照 */
export function restoreSnapshot(workId: number, snapshotId: number) {
  return http.post<{ restored: number; applied: number }>(
    `/works/${workId}/snapshots/${snapshotId}/restore`,
  )
}

/** 逐条回滚（最小回滚单位：一条 EditLog 的一个字段） */
export function rollbackEdit(workId: number, logId: number) {
  return http.post<{ reverted: boolean; object_type: string; object_id: number | null; field: string }>(
    `/works/${workId}/edits/${logId}/rollback`,
  )
}
