import http from './request'

// GET /voices —— 音色库（POC 为 3 个内置音色：旁白·中性 / 男声·青年 / 女声·青年）
export function listVoices(params?: {
  tags?: string
  type?: string
  page?: number
  page_size?: number
}) {
  return http.get('/voices', { params })
}
