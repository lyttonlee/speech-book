import http from './request'

export function getTask(taskId: string) {
  return http.get(`/tasks/${taskId}`)
}
