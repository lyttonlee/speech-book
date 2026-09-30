import { onUnmounted, ref, toValue, type MaybeRefOrGetter } from 'vue'
import { useUserStore } from '@/stores/user'

// 订阅后端任务 SSE 进度流（docs/接口文档.md §12.3）
// token 走 query（浏览器 EventSource 不支持自定义头）
export function useTaskSSE(taskId: MaybeRefOrGetter<string>) {
  const progress = ref(0)
  const stage = ref('')
  const done = ref(false)
  const failed = ref(false)
  const errorMsg = ref('')

  let es: EventSource | null = null

  function connect() {
    const id = toValue(taskId)
    if (!id) return
    const token = useUserStore().token
    es = new EventSource(`/api/v1/tasks/${id}/stream?token=${token}`)
    es.addEventListener('progress', (e: MessageEvent) => {
      const d = JSON.parse(e.data)
      progress.value = d.progress ?? progress.value
      if (d.stage) stage.value = d.stage
    })
    es.addEventListener('done', () => {
      done.value = true
      es?.close()
    })
    es.addEventListener('error', (e: MessageEvent) => {
      try {
        const d = JSON.parse(e.data)
        failed.value = true
        errorMsg.value = d.message || '任务失败'
      } catch {
        failed.value = true
      }
      es?.close()
    })
  }

  function close() {
    es?.close()
    es = null
  }

  onUnmounted(close)
  return { progress, stage, done, failed, errorMsg, connect, close }
}
