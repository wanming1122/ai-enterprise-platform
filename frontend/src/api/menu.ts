import { del, get, post, put } from '@/api/request'
import type { PageResult } from '@/types'

/** 菜单节点 */
export interface MenuItem2 {
  id: number
  parent_id: number | null
  name: string
  type: number
  path?: string | null
  component?: string | null
  icon?: string | null
  permission_code?: string | null
  visible?: number
  is_external?: number
  sort_order?: number
  status?: number
  children?: MenuItem2[]
}

export interface MenuForm {
  parent_id?: number | null
  name?: string
  type?: number
  path?: string | null
  component?: string | null
  icon?: string | null
  permission_code?: string | null
  visible?: number
  is_external?: number
  sort_order?: number
  status?: number
}

export interface MenuSortItem {
  id: number
  sort_order: number
}

/** 权限标识 */
export interface PermItem {
  id: number
  name: string
  code: string
  module?: string
  description?: string
  status?: number
}

export const MENU_TYPE_TEXT: Record<number, { text: string; color: string }> = {
  1: { text: '目录', color: 'blue' },
  2: { text: '页面', color: 'green' },
  3: { text: '按钮', color: 'purple' },
}

export const menuApi = {
  tree: () => get<MenuItem2[]>('/menus/tree'),
  create: (data: MenuForm) => post<MenuItem2>('/menus', data),
  update: (id: number, data: MenuForm) => put<MenuItem2>(`/menus/${id}`, data),
  remove: (id: number) => del<null>(`/menus/${id}`),
  toggleStatus: (id: number) => put<MenuItem2>(`/menus/${id}/status`),
  sort: (items: MenuSortItem[]) => post<null>('/menus/sort', items),
  permissions: (params: { keyword?: string; page: number; page_size: number }) =>
    get<PageResult<PermItem>>('/permissions', { params }),
  createPerm: (data: Partial<PermItem>) => post<PermItem>('/permissions', data),
  updatePerm: (id: number, data: Partial<PermItem>) => put<PermItem>(`/permissions/${id}`, data),
  removePerm: (id: number) => del<null>(`/permissions/${id}`),
}
