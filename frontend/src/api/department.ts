import { del, get, post, put } from '@/api/request'

/** 部门树节点 */
export interface DeptItem {
  id: number
  name: string
  parent_id: number | null
  leader_id?: number | null
  leader_name?: string
  phone?: string
  email?: string
  description?: string
  sort_order?: number
  status?: number
  children?: DeptItem[]
}

/** 部门表单数据（新增/编辑） */
export interface DeptForm {
  name?: string
  parent_id?: number | null
  leader_id?: number | null
  phone?: string
  email?: string
  description?: string
  sort_order?: number
  status?: number
}

export interface DeptSortItem {
  id: number
  sort_order: number
}

/** 用户下拉选项（部门负责人） */
export interface UserOption {
  id: number
  username: string
  real_name: string
}

export const deptApi = {
  tree: () => get<DeptItem[]>('/departments/tree'),
  create: (data: DeptForm) => post<DeptItem>('/departments', data),
  update: (id: number, data: DeptForm) => put<DeptItem>(`/departments/${id}`, data),
  remove: (id: number) => del<null>(`/departments/${id}`),
  toggleStatus: (id: number) => put<DeptItem>(`/departments/${id}/status`),
  sort: (items: DeptSortItem[]) => post<null>('/departments/sort', items),
  users: () => get<UserOption[]>('/users/options'),
}
