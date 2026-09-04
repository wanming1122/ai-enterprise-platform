import type { Dayjs } from 'dayjs'
import { del, downloadBlob, get, post, put } from '@/api/request'
import type { PageResult, UserInfo } from '@/types'

/** 部门选项（树） */
export interface DeptOption {
  id: number
  name: string
  parent_id: number | null
  children?: DeptOption[]
}

/** 角色选项 */
export interface RoleOption {
  id: number
  name: string
  code: string
}

/** 用户列表筛选参数 */
export interface UserQuery {
  keyword?: string
  department_id?: number
  role_id?: number
  status?: number
  page: number
  page_size: number
}

/** 用户表单数据（新增/编辑） */
export interface UserForm {
  username?: string
  password?: string
  real_name?: string
  nickname?: string
  gender?: number
  /** 表单回填为 Dayjs，提交时转 'YYYY-MM-DD' 字符串 */
  birthday?: Dayjs | string | null
  email?: string
  phone?: string
  department_id?: number
  post?: string
  role_ids?: number[]
}

/** 导入结果 */
export interface ImportResult {
  total: number
  success: number
  failed: number
  errors: { row: number; reason: string }[]
}

export const userApi = {
  list: (params: UserQuery) => get<PageResult<UserInfo>>('/users', { params }),
  create: (data: UserForm) => post<UserInfo>('/users', data),
  update: (id: number, data: UserForm) => put<UserInfo>(`/users/${id}`, data),
  remove: (id: number) => del<null>(`/users/${id}`),
  toggleStatus: (id: number) => put<UserInfo>(`/users/${id}/status`),
  resetPassword: (id: number) => put<{ user_id: number; temp_password: string }>(`/users/${id}/reset-password`),
  importUsers: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return post<ImportResult>('/users/import', form)
  },
  exportUsers: (params: Partial<UserQuery>) => downloadBlob('/users/export', params),
  downloadTemplate: () => downloadBlob('/users/template'),
  departments: () => get<DeptOption[]>('/departments/options'),
  roles: () => get<RoleOption[]>('/roles/options'),
}

/** 触发浏览器下载 Blob 文件 */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
