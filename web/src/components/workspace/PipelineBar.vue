<template>
<!--FRAG:pipeline-->
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import type { PipelineStage, StageAction } from '@/types'

/**
 * 六段制作流水线（design/workspace.html §2）。
 *
 * 每段显示耗时 / 状态徽标，点击滚到对应区块；
 * 每段自带「人工介入」按钮，目的是让用户不用退回新建向导也能介入当前段。
 */

const props = defineProps<{ workId: number }>()
const emit = defineEmits<{
  go: [id: string]
  rerun: []
  synth: []
}>()

const store = useWorkStore()
const router = useRouter()

/** 流水线六段 → 点击后跳到哪个区块 */
const STAGE_ANCHOR: Record<string, string> = {
  upload: 'chapters',
  parse: 'chapters',
  proofread: 'chapters',
  cast: 'cast',
  synth: 'audio',
  export: 'export',
}

/** 流水线某段的耗时文案：有耗时显示耗时，否则显示进度 */
function stageTime(st: PipelineStage): string {
  if (st.seconds) return fmtSeconds(st.seconds)
  if (st.status === 'done') return '完成'
  if (st.status === 'active') return `${st.progress}%`
  return '未开始'
}

/** 秒 → `mm:ss`（秒数不大时直接 `Ns` 也够读，这里统一补零） */
function fmtSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`
  const m = Math.floor(s / 60)
  return `${m}m${String(Math.round(s % 60)).padStart(2, '0')}s`
}

/** 状态 → 徽标配色类 */
function stageBadge(st: PipelineStage): string {
  if (st.status === 'done') return 'badge ok'
  if (st.status === 'active') return 'badge info'
  if (st.status === 'error') return 'badge warn'
  return 'badge'
}

function stageStatusText(st: PipelineStage): string {
  return { done: '完成', active: '进行中', idle: '未开始', error: '失败' }[st.status] ?? '未开始'
}

/**
 * 流水线的人工介入动作（DESIGN_SPEC §5.3b：不用回到向导页就能介入）。
 * 每个动作都落到真实接口或滚到对应区块，不做假按钮。
 */
async function onStageAction(st: PipelineStage, action: StageAction) {
  switch (action.key) {
    case 'reupload':
      // 重新上传文本走新建向导（POC 未做「替换文本」接口）
      router.push('/studio')
      break
    case 'rerun':
      emit('rerun')
      break
    case 'review':
      emit('go', 'chapters')
      break
    case 'rebind':
      await store.autoBind(props.workId)
      ElMessage.success('已按音色标签重新推荐绑定')
      break
    case 'speedup':
      emit('synth')
      break
    case 'preset':
      emit('go', 'export')
      break
    default:
      ElMessage.info(`${st.label} · ${action.label}`)
  }
}
</script>
