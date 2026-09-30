import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

// 统一信封：{ code, data, request_id } —— 见 docs/接口文档.md §1.3
const instance: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

instance.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  const token = useUserStore().token
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// 拦截器：把后端信封拆成 data 返回；非 OK 直接 reject 并提示
instance.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && body.code && body.code !== 'OK') {
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(body)
    }
    return (body?.data ?? body) as any
  },
  (err) => {
    const msg = err?.response?.data?.message || err?.message || '网络错误'
    ElMessage.error(msg)
    return Promise.reject(err)
  },
)

// 响应拦截器已把 { code, data, ... } 信封拆成 data 返回，因此此处方法返回类型
// 声明为 Promise<T>（默认 any），与运行时一致，避免到处 .data 取值的类型报错。
export interface ApiClient {
  get: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<T>
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<T>
  head: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<T>
  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<T>
  put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<T>
  patch: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<T>
  interceptors: AxiosInstance['interceptors']
}

export const http = instance as unknown as ApiClient
export default http
