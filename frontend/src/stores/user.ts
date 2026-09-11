import { create } from 'zustand'
import type { AxiosError } from 'axios'
import { message } from 'antd'
import { clearTokens, get, getAccessToken, getRefreshToken, post, setTokens } from '@/api/request'
import type { LoginResult, MenuItem, UserInfo } from '@/types'

interface UserState {
  /** 当前访问令牌 */
  token: string
  userInfo: UserInfo | null
  menus: MenuItem[]
  permissions: string[]
  /** 会话恢复是否完成（应用启动时决定是否跳登录页） */
  initialized: boolean
  /** 账号密码登录 */
  login: (username: string, password: string) => Promise<void>
  /** 退出登录：通知后端作废刷新令牌并清空本地会话 */
  logout: () => Promise<void>
  /** 写入会话数据（登录成功后调用） */
  setSession: (data: LoginResult) => void
  /** 启动时用已有令牌恢复用户/菜单/权限 */
  initSession: () => Promise<void>
  /** 更新本地用户信息（个人资料修改后调用） */
  updateUserInfo: (user: UserInfo) => void
}

export const useUserStore = create<UserState>((set) => ({
  token: getAccessToken() ?? '',
  userInfo: null,
  menus: [],
  permissions: [],
  initialized: false,

  login: async (username: string, password: string) => {
    const data = await post<LoginResult>('/auth/login', { username, password })
    setTokens(data.access_token, data.refresh_token)
    set({
      token: data.access_token,
      userInfo: data.user,
      menus: data.menus,
      permissions: data.permissions,
      initialized: true,
    })
  },

  logout: async () => {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      try {
        await post('/auth/logout', { refresh_token: refreshToken })
      } catch {
        // 后端作废失败不阻塞前端退出
      }
    }
    clearTokens()
    set({ token: '', userInfo: null, menus: [], permissions: [], initialized: true })
  },

  setSession: (data: LoginResult) => {
    setTokens(data.access_token, data.refresh_token)
    set({
      token: data.access_token,
      userInfo: data.user,
      menus: data.menus,
      permissions: data.permissions,
      initialized: true,
    })
  },

  initSession: async () => {
    const token = getAccessToken()
    if (!token) {
      set({ initialized: true })
      return
    }
    // 仅当服务端明确判定会话无效（401/403）才清理本地令牌；
    // 网络错误/后端未就绪（5xx、超时）视为暂时不可达，保留令牌并短暂重试，
    // 否则一键启动后端尚未就绪时打开页面会把用户误判为未登录并强制退出。
    const MAX_ATTEMPTS = 3
    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
      try {
        const data = await get<{ user: UserInfo; menus: MenuItem[]; permissions: string[] }>(
          '/auth/me',
          { silentAuth: true },
        )
        // /auth/me 可能触发拦截器内 401 刷新并轮换了 token，取最新值回写，避免 store 留旧令牌
        set({
          token: getAccessToken() ?? token,
          userInfo: data.user,
          menus: data.menus,
          permissions: data.permissions,
          initialized: true,
        })
        return
      } catch (e) {
        const status = (e as AxiosError)?.response?.status
        if (status === 401 || status === 403) {
          clearTokens()
          set({ token: '', userInfo: null, menus: [], permissions: [], initialized: true })
          return
        }
        if (attempt < MAX_ATTEMPTS - 1) {
          await new Promise((resolve) => setTimeout(resolve, 800 * (attempt + 1)))
          continue
        }
        // 多次仍不可达：保留 localStorage 中的令牌，本次回到登录页；
        // 用户刷新页面（后端就绪后）即可自动恢复会话，无需重新输入密码
        set({ token: '', userInfo: null, menus: [], permissions: [], initialized: true })
        message.error('服务连接失败，请刷新页面重试')
      }
    }
  },

  updateUserInfo: (user: UserInfo) => {
    set({ userInfo: user })
  },
}))
