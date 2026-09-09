import { del, get, post, put } from '@/api/request'
import type { PageResult } from '@/types'

export interface RoleItem {
  id: number
  name: string
  code: string
  role_type: number
  data_scope: number
  description?: string
  status?: number
  user_count?: number
  created_at?: string | null
}

export interface RoleForm {
  name?: string
  code?: string
  role_type?: number
  data_scope?: number
  description?: string
  status?: number
}

export const ROLE_TYPE_TEXT: Record<number, string> = {
  1: '超级管理员',
  2: '普通管理员',
  3: '普通员工',
}

export const DATA_SCOPE_TEXT: Record<number, string> = {
  1: '仅本人',
  2: '本部门',
  3: '全部',
}

export const roleApi = {
  list: (params: { keyword?: string; page: number; page_size: number }) =>
    get<PageResult<RoleItem>>('/roles', { params }),
  create: (data: RoleForm) => post<RoleItem>('/roles', data),
  update: (id: number, data: RoleForm) => put<RoleItem>(`/roles/${id}`, data),
  remove: (id: number) => del<null>(`/roles/${id}`),
  toggleStatus: (id: number) => put<RoleItem>(`/roles/${id}/status`),
  authorize: (id: number, menuIds: number[]) => put<null>(`/roles/${id}/menus`, { menu_ids: menuIds }),
  menus: (id: number) => get<number[]>(`/roles/${id}/menus`),
}
