import { create } from 'zustand'
import request, { clearTokens, getAccessToken, setTokens } from '@/api/request'
import type { LoginResult, MenuItem, UserInfo } from '@/types'

interface UserState {
  /** 当前访问令牌 */
  token: string
  userInfo: UserInfo | null
  menus: MenuItem[]
  permissions: string[]
  /** 账号密码登录（认证接口在 M1 落地） */
  login: (username: string, password: string) => Promise<void>
  /** 退出登录：清空令牌与本地状态 */
  logout: () => void
  /** 写入会话数据（登录成功后调用） */
  setSession: (data: LoginResult) => void
}

export const useUserStore = create<UserState>((set) => ({
  token: getAccessToken() ?? '',
  userInfo: null,
  menus: [],
  permissions: [],

  login: async (username: string, password: string) => {
    const data = await request
      .post<LoginResult>('/auth/login', { username, password })
      .then((res) => res.data)
    set({ token: data.access_token })
    setTokens(data.access_token, data.refresh_token)
    set({ userInfo: data.user, menus: data.menus, permissions: data.permissions })
  },

  logout: () => {
    clearTokens()
    set({ token: '', userInfo: null, menus: [], permissions: [] })
  },

  setSession: (data: LoginResult) => {
    set({ token: data.access_token })
    setTokens(data.access_token, data.refresh_token)
    set({ userInfo: data.user, menus: data.menus, permissions: data.permissions })
  },
}))