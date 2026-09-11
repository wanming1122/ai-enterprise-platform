import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { message } from 'antd'
import type { ApiResponse } from '@/types'

/** 令牌存取：access（30分钟）/ refresh（7天，轮换） */
const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

/** 刷新失败原因：auth=服务端明确判定令牌无效（需重新登录）；network=网络/服务不可达（会话应保留） */
export class RefreshError extends Error {
  readonly kind: 'auth' | 'network'

  constructor(kind: 'auth' | 'network', message: string) {
    super(message)
    this.name = 'RefreshError'
    this.kind = kind
  }
}

/** 会话失效处理是否已执行：并发 401 只弹一条提示、只跳转一次 */
let sessionExpiredHandled = false

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  // 拿到新令牌说明会话有效，重置标记，使后续真正失效时仍能提示一次
  sessionExpiredHandled = false
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

/** 会话失效统一出口：清理本地令牌并回登录页。
 *  - 去重：并发请求同时 401 时只提示一次、只跳转一次（否则切换页面会连弹多条）
 *  - silent：应用启动时用残留令牌静默恢复会话，用户并未操作，不再弹"登录已过期" */
function handleSessionExpired(silent = false): void {
  if (sessionExpiredHandled) return
  sessionExpiredHandled = true
  clearTokens()
  if (window.location.pathname.startsWith('/login')) return
  if (!silent) message.error('登录已过期，请重新登录')
  window.location.href = '/login'
}

/** 请求配置扩展：silentAuth=true 表示会话恢复探测，401 时不弹"登录已过期"提示（用户并未在操作） */
export interface ApiRequestConfig extends AxiosRequestConfig {
  silentAuth?: boolean
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

/** 无拦截器的裸实例：仅用于刷新令牌，避免刷新请求触发 401 循环 */
const raw = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

/** 刷新令牌单例：并发 401 只触发一次刷新 */
let refreshPromise: Promise<string> | null = null

/** 刷新访问令牌：axios 拦截器与 SSE fetch（streamKBChat）共用。
 *  失败时区分"服务端拒绝（401/403，令牌确实失效）"与"网络/服务不可达"：
 *  后者绝不能清空本地令牌，否则后端重启、一键启动瞬间或短暂断网会把用户误踢回登录页。 */
export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshToken = getRefreshToken()
      if (!refreshToken) throw new RefreshError('auth', '无刷新令牌')
      try {
        const res = await raw.post<ApiResponse<{ access_token: string; refresh_token: string }>>(
          '/auth/refresh',
          { refresh_token: refreshToken },
        )
        const data = res.data.data
        if (!data?.access_token || !data?.refresh_token) {
          throw new RefreshError('auth', '刷新响应无效')
        }
        setTokens(data.access_token, data.refresh_token)
        return data.access_token
      } catch (e) {
        if (e instanceof RefreshError) throw e
        const status = (e as AxiosError)?.response?.status
        if (status === 401 || status === 403) throw new RefreshError('auth', '登录已过期')
        throw new RefreshError('network', '无法连接服务器')
      }
    })().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

// 请求拦截器：自动携带 Bearer Token
request.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一业务响应处理 + 401 无感刷新重放 + 统一错误提示
request.interceptors.response.use(
  (response) => {
    const res = response.data as ApiResponse
    if (res.code === 0) {
      return response
    }
    if (res.code !== 401) {
      message.error(res.message || '请求失败')
    }
    return Promise.reject(new Error(res.message || '请求失败'))
  },
  async (error: AxiosError<ApiResponse>) => {
    const status = error.response?.status
    const config = error.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean; silentAuth?: boolean })
      | undefined
    const isLogin = config?.url?.includes('/auth/login')

    // 401 且非登录接口：尝试刷新令牌后重放原请求
    if (status === 401 && config && !config._retried && !isLogin) {
      try {
        const newToken = await refreshAccessToken()
        config._retried = true
        config.headers.Authorization = `Bearer ${newToken}`
        return request(config)
      } catch (e) {
        // 网络/服务不可达：保留本地令牌，只提示不登出（后端未就绪、断网均属此类）
        if (e instanceof RefreshError && e.kind === 'network') {
          message.error('无法连接服务器，请检查网络后重试')
          return Promise.reject(error)
        }
        handleSessionExpired(config.silentAuth === true)
        return Promise.reject(error)
      }
    }

    // 登录接口的错误由登录页自行常驻展示（含锁定倒计时），拦截器不再弹 toast
    if (isLogin) {
      return Promise.reject(error)
    }

    const msg = error.response?.data?.message || '请求失败'
    if (status === 401) {
      handleSessionExpired(config?.silentAuth === true)
    } else {
      message.error(msg === '请求失败' ? '网络异常，请稍后重试' : msg)
    }
    return Promise.reject(error)
  },
)

/** 类型化 GET：直接返回业务 data */
export async function get<T>(url: string, config?: ApiRequestConfig): Promise<T> {
  const res = await request.get<ApiResponse<T>>(url, config)
  return res.data.data
}

/** 类型化 POST：直接返回业务 data */
export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const res = await request.post<ApiResponse<T>>(url, data, config)
  return res.data.data
}

/** 类型化 PUT：直接返回业务 data */
export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const res = await request.put<ApiResponse<T>>(url, data, config)
  return res.data.data
}

/** 类型化 DELETE：直接返回业务 data */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await request.delete<ApiResponse<T>>(url, config)
  return res.data.data
}

/** 类型化 PATCH：直接返回业务 data */
export async function patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const res = await request.patch<ApiResponse<T>>(url, data, config)
  return res.data.data
}

/** 文件下载（导出/模板）：返回 Blob，由调用方触发浏览器下载。
 *  Blob 响应无法走统一拦截器的 {code,message,data} 解包，这里手动补齐：
 *  401 → 无感刷新后重放一次；失败弹统一错误提示；导出可能较慢，超时放宽到 120s。 */
export async function downloadBlob(
  url: string,
  params?: Record<string, unknown>,
): Promise<Blob> {
  const attempt = (token: string | null) =>
    raw.get<Blob>(url, {
      params,
      responseType: 'blob',
      timeout: 120000,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
  let res
  try {
    res = await attempt(getAccessToken())
  } catch (e) {
    if ((e as AxiosError)?.response?.status !== 401) {
      message.error('下载失败，请稍后重试')
      throw e
    }
    let newToken: string
    try {
      newToken = await refreshAccessToken()
    } catch (e) {
      // 网络/服务不可达时不清理令牌，避免短暂断网导致退出登录
      if (e instanceof RefreshError && e.kind === 'network') {
        message.error('无法连接服务器，请检查网络后重试')
        throw new Error('无法连接服务器')
      }
      handleSessionExpired()
      throw new Error('登录已过期')
    }
    try {
      res = await attempt(newToken)
    } catch {
      message.error('下载失败，请稍后重试')
      throw new Error('下载失败')
    }
  }
  return res.data
}

export default request
