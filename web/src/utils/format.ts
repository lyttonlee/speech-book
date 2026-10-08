/**
 * 通用格式化工具（跨页面复用，避免每个组件各写一份）。
 *
 * 约定：纯展示函数，不碰 store、不发请求，保持可单测。
 */

/**
 * ISO 时间字符串 → `MM-DD HH:mm`。
 * 列表 / 日志场景只看得到分钟，秒和年份是噪音。
 */
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 字节数 → KB / MB（POC 音频资产都在 MB 级，KB 只作兜底） */
export function fmtSize(bytes: number): string {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

/**
 * 生成一组确定性的波形柱高度。
 *
 * 设计稿用 JS 随机生成，但随机数每次渲染都会变，波形会「跳」；
 * 这里改成按 seed 计算，保证同一份数据渲染出来的波形稳定。
 */
export function mkBars(count: number, seed = 1): number[] {
  return Array.from({ length: count }, (_, i) =>
    Math.round(18 + Math.abs(Math.sin(i * 0.45 * seed + seed) * 0.8 + Math.sin(i * 0.13) * 0.2) * 70),
  )
}
