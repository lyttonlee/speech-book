import http from './request'

export function startParse(workId: number) {
  return http.post(`/works/${workId}/parse`)
}
export function getRoles(workId: number) {
  return http.get(`/works/${workId}/roles`)
}
export function getSegments(workId: number) {
  return http.get(`/works/${workId}/parse/segments`)
}
export function getReviewItems(workId: number, lowConfOnly = true) {
  return http.get(`/works/${workId}/parse/review-items`, {
    params: { low_conf_only: lowConfOnly },
  })
}
