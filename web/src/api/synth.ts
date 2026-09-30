import http from './request'

export function startSynth(workId: number, scope: 'sample' | 'full' | 'range' = 'sample') {
  return http.post(`/works/${workId}/synthesize`, { scope })
}
export function synthStatus(workId: number, taskId: string) {
  return http.get(`/works/${workId}/synthesize/${taskId}`)
}
