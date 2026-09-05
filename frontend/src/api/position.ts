import { del, get, post, put } from '@/api/request'
import type { PageResult } from '@/types'

/** 职位列表项 */
export interface PositionItem {
  id: number
  name: string
  code: string
  level: number
  base_salary: string
  role_id?: number | null
  role_name?: string | null
  description?: string | null
  status: number
  user_count?: number
  created_at?: string | null
}

/** 职位表单数据（新增/编辑） */
export interface PositionForm {
  name?: string
  code?: string
  level?: number
  base_salary?: string
  role_id?: number | null
  description?: string
  status?: number
}

/** 职位下拉选项 */
export interface PositionOption {
  id: number
  name: string
  level: number
  base_salary: string
  role_id?: number | null
  role_name?: string | null
}

export const positionApi = {
  list: (params: {
    keyword?: string
    role_id?: number
    status?: number
    page: number
    page_size: number
  }) => get<PageResult<PositionItem>>('/positions', { params }),
  create: (data: PositionForm) => post<PositionItem>('/positions', data),
  update: (id: number, data: PositionForm) => put<PositionItem>(`/positions/${id}`, data),
  remove: (id: number) => del<null>(`/positions/${id}`),
  toggleStatus: (id: number) => put<PositionItem>(`/positions/${id}/status`),
  options: () => get<PositionOption[]>('/positions/options'),
  roleOptions: () => get<{ id: number; name: string; code: string }[]>('/positions/role-options'),
}
