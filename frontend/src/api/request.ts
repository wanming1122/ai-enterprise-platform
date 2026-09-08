import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { message } from 'antd'
import type { ApiResponse } from '@/types'

/** 令牌存取：access（30分钟）/ refresh（7天，轮换） */
const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
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

/** 刷新访问令牌：axios 拦截器与 SSE fetch（streamKBChat）共用 */
export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshToken = getRefreshToken()
      if (!refreshToken) throw new Error('无刷新令牌')
      const res = await raw.post<ApiResponse<{ access_token: string; refresh_token: string }>>(
        '/auth/refresh',
        { refresh_token: refreshToken },
      )
      const data = res.data.data
      setTokens(data.access_token, data.refresh_token)
      return data.access_token
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
    const config = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const isLogin = config?.url?.includes('/auth/login')

    // 401 且非登录接口：尝试刷新令牌后重放原请求
    if (status === 401 && config && !config._retried && !isLogin) {
      try {
        const newToken = await refreshAccessToken()
        config._retried = true
        config.headers.Authorization = `Bearer ${newToken}`
        return request(config)
      } catch {
        clearTokens()
        if (!window.location.pathname.startsWith('/login')) {
          message.error('登录已过期，请重新登录')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    }

    const msg = error.response?.data?.message || '请求失败'
    if (status === 401) {
      // 登录接口 401（密码错误等）：提示但不跳转
      if (!window.location.pathname.startsWith('/login')) {
        message.error('登录已过期，请重新登录')
        window.location.href = '/login'
      } else {
        message.error(msg)
      }
    } else {
      message.error(msg === '请求失败' ? '网络异常，请稍后重试' : msg)
    }
    return Promise.reject(error)
  },
)

/** 类型化 GET：直接返回业务 data */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
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

/** 文件下载（导出/模板）：返回 Blob，由调用方触发浏览器下载 */
export async function downloadBlob(
  url: string,
  params?: Record<string, unknown>,
): Promise<Blob> {
  const token = getAccessToken()
  const res = await raw.get<Blob>(url, {
    params,
    responseType: 'blob',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  return res.data
}

export default request
