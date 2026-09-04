import { create } from 'zustand'
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
    try {
      const data = await get<{ user: UserInfo; menus: MenuItem[]; permissions: string[] }>('/auth/me')
      set({ token, userInfo: data.user, menus: data.menus, permissions: data.permissions, initialized: true })
    } catch {
      clearTokens()
      set({ token: '', userInfo: null, menus: [], permissions: [], initialized: true })
    }
  },
}))
