import { get, put } from '@/api/request'
import type { PageResult, UserInfo } from '@/types'
import type { AttRecordItem } from '@/api/attendance'
import type { SalaryDetail, SalaryItem } from '@/api/salary'

/** 本人资料修改（不含账号/部门/职位/角色等管理字段） */
export interface ProfileUpdate {
  nickname?: string
  real_name?: string
  gender?: number
  birthday?: string | null
  email?: string
  phone?: string
  social_account?: string
  avatar?: string
}

export const profileApi = {
  update: (data: ProfileUpdate) => put<UserInfo>('/profile', data),
  changePassword: (data: { old_password: string; new_password: string }) =>
    put<null>('/profile/password', data),
  attendance: (params: { month?: string; page: number; page_size: number }) =>
    get<PageResult<AttRecordItem>>('/profile/attendance', { params }),
  salaries: (params: { year_month?: string; page: number; page_size: number }) =>
    get<PageResult<SalaryItem>>('/profile/salary', { params }),
  salaryDetail: (id: number) => get<SalaryDetail>(`/profile/salary/${id}`),
}
