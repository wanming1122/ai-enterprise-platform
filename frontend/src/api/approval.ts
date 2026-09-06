import type { PageResult } from '@/types'
import { get, post } from './request'

export interface ApprovalItem {
  id: number
  user_id: number
  username: string
  real_name: string | null
  phone: string | null
  email: string | null
  apply_role_id: number
  apply_role_name: string | null
  status: 0 | 1 | 2
  status_label: string
  apply_comment: string | null
  review_comment: string | null
  reviewer: string | null
  reviewed_at: string | null
  account_status: number | null
  created_at: string
}

export interface RegisterRoleOption {
  id: number
  name: string
}

export const approvalApi = {
  list: (params: { status?: number; keyword?: string; page?: number; page_size?: number }) =>
    get<PageResult<ApprovalItem>>('/approvals', { params }),
  approve: (id: number) => post<ApprovalItem>(`/approvals/${id}/approve`),
  reject: (id: number, comment?: string) =>
    post<ApprovalItem>(`/approvals/${id}/reject`, { comment: comment || undefined }),
  /** 公开：可申请角色与提交注册申请（无需登录） */
  registerOptions: () => get<RegisterRoleOption[]>('/auth/register-options'),
  registerApply: (data: {
    username: string
    password: string
    real_name: string
    phone?: string
    email?: string
    apply_role_id: number
    apply_comment?: string
  }) => post<ApprovalItem>('/auth/register-apply', data),
}
