<template>
<!--FRAG:audit-->
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import { fmtTime } from '@/utils/format'
import type { EditLog } from '@/types'

/**
 * 人工修改留痕与版本快照（design/workspace.html §9）。
 *
 * 每条人工改动都是一条留痕（可逐条回滚）；
 * 另外提供「版本快照」做整体回滚 —— 破坏性操作，走二次确认。
 */

const props = defineProps<{ workId: number }>()

const store = useWorkStore()

/** 下一个版本号：当前最大版本 + 1（用来给快照命名） */
const currentVersion = computed(() => {
  const max = store.snapshots.reduce((m, s) => Math.max(m, s.version), 0)
  return max + 1
})

/** 留痕类型 → 徽标配色 */
function editTone(e: EditLog): string {
  if (e.action === 'revert') return 'info'
  if (e.field === 'text') return 'acc'
  if (e.field === 'emotion' || e.field === 'intensity') return 'info'
  return 'warn'
}

/** 留痕类型文案 */
function editLabel(e: EditLog): string {
  const map: Record<string, string> = {
    text: '改文本', speaker_role_id: '改说话人', speaker_name: '改说话人',
    emotion: '改情绪', intensity: '改情绪强度', confidence: '确认置信',
    type: '改类型', voice_id: '改绑定', level: '改角色级别', name: '改角色名',
    label: '改关系', kind: '改关系类型', weight: '改关系强度', deleted: '删除',
  }
  return map[e.field] ?? (e.object_type === 'segment' ? '改片段' : '人工调整')
}

/** 留痕对象文案：片段显示 id，其它显示对象类型 */
function editObject(e: EditLog): string {
  const typeMap: Record<string, string> = {
    segment: '片段', role: '角色', binding: '绑定', relation: '关系', work: '作品',
  }
  return `${typeMap[e.object_type] ?? e.object_type} #${e.object_id ?? '—'}`
}

/** 长文本截断，避免 diff 列撑爆表格 */
function trim(v: string | null): string {
  if (!v) return '—'
  return v.length > 24 ? `${v.slice(0, 24)}…` : v
}

/** 逐条回滚某处修改 */
async function rollback(e: EditLog) {
  await store.rollbackEdit(props.workId, e.id)
  ElMessage.success('已回滚该处修改')
}

/** 整体回滚到某个版本快照（破坏性操作，二次确认） */
async function restoreSnapshot(s: { id: number; version: number }) {
  try {
    await ElMessageBox.confirm(
      `回滚到 v${s.version} 会覆盖之后的所有人工修改，确定吗？`,
      '版本回滚',
      { type: 'warning', confirmButtonText: '回滚', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await store.restoreSnapshot(props.workId, s.id)
  ElMessage.success(`已回滚到 v${s.version}`)
}

/** 保存当前状态为一个版本快照 */
async function saveSnapshot() {
  try {
    const { value } = await ElMessageBox.prompt('给这个版本起个名字', '保存快照', {
      inputValue: `人工保存 v${currentVersion.value}`,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    await store.createSnapshot(props.workId, value || `人工保存 v${currentVersion.value}`)
    ElMessage.success('快照已保存')
  } catch {
    /* 用户取消 */
  }
}

/** 导出修改日志 CSV */
function exportLogs() {
  const head = '时间,类型,对象,原值,新值,动作\n'
  const body = store.edits.map((e) =>
    [fmtTime(e.created_at), editLabel(e), editObject(e), e.old_value ?? '', e.new_value ?? '', e.action].join(','),
  ).join('\n')
  const url = URL.createObjectURL(new Blob([head + body], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `${store.currentWork?.name ?? 'work'}-edits.csv`
  a.click()
  URL.revokeObjectURL(url)
}
</script>
