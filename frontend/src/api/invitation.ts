import type { PageResult } from '@/types'
import { get, post, del } from './request'

export interface InvitationItem {
  id: number
  name: string
  phone: string | null
  email: string | null
  department_id: number | null
  department_name: string | null
  role_id: number | null
  role_name: string | null
  post: string | null
  token: string
  invite_link: string | null
  expires_at: string | null
  status: number
  status_label: string
  remark: string | null
  created_at: string
}

export interface InvitationLogItem {
  id: number
  action: string
  detail: string | null
  ip: string | null
  created_at: string
}

export const INVITATION_STATUS_COLOR: Record<number, string> = {
  0: 'default',
  1: 'processing',
  2: 'warning',
  3: 'success',
  4: 'default',
  5: 'error',
  6: 'error',
}

export const invitationApi = {
  list: (params: { status?: number; keyword?: string; page?: number; page_size?: number }) =>
    get<PageResult<InvitationItem>>('/invitations', { params }),
  create: (data: {
    name: string
    phone?: string
    email?: string
    department_id?: number
    role_id?: number
    post?: string
    expires_days?: number
    remark?: string
  }) => post<InvitationItem>('/invitations', data),
  resend: (id: number) => post<InvitationItem>(`/invitations/${id}/resend`),
  cancel: (id: number) => post<InvitationItem>(`/invitations/${id}/cancel`),
  remove: (id: number) => del(`/invitations/${id}`),
  logs: (id: number) => get<InvitationLogItem[]>(`/invitations/${id}/logs`),
  /** 公开：邀请信息与接受注册（无需登录） */
  publicInfo: (token: string) =>
    get<{
      name: string
      department_name: string | null
      role_name: string | null
      post: string | null
      status: number
      status_label: string
      expires_at: string | null
    }>(`/invitations/public/${token}`),
  publicAccept: (token: string, data: { username: string; password: string }) =>
    post<{ username: string; real_name: string }>(`/invitations/public/${token}/accept`, data),
}
