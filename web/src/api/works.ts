import http from './request'

export function createWork(payload: { name: string; author?: string; type?: string }) {
  return http.post('/works', payload)
}
export function getWork(workId: number) {
  return http.get(`/works/${workId}`)
}
export function mergeText(workId: number, filename: string, content: string) {
  return http.post(`/works/${workId}/files/merge`, { filename, content })
}
export function getText(workId: number) {
  return http.get(`/works/${workId}/files/text`)
}
