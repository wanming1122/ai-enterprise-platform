import { get, post, put } from '@/api/request'
import type { PageResult } from '@/types'

/** 工资单列表项 */
export interface SalaryItem {
  id: number
  user_id: number
  username?: string
  real_name?: string | null
  dept_name?: string | null
  year_month: string
  position_name: string
  base_salary: string
  attendance_adjust: string
  manual_adjust: string
  total_salary: string
  status: number
  status_label: string
  confirmed_at?: string | null
  created_at?: string | null
}

/** 工资单明细 */
export interface SalaryDetail {
  payroll: SalaryItem
  attendance_items: {
    att_date: string
    status: string
    status_label: string
    adjust_type: number
    amount: string
    delta: string
  }[]
  adjustment_items: {
    id: number
    adjust_type: number
    adjust_type_label: string
    amount: string
    reason: string
    year_month?: string | null
    created_at?: string | null
  }[]
}

/** 奖惩列表项 */
export interface AdjustmentItem {
  id: number
  user_id: number
  username?: string
  real_name?: string | null
  adjust_type: number
  adjust_type_label: string
  amount: string
  delta: string
  reason: string
  year_month?: string | null
  created_at?: string | null
}

/** 生成结果 */
export interface GenerateResult {
  year_month: string
  generated: number
  locked: number
  no_position: string[]
}

export const salaryApi = {
  list: (params: {
    year_month?: string
    department_id?: number
    user_id?: number
    status?: number
    page: number
    page_size: number
  }) => get<PageResult<SalaryItem>>('/salaries', { params }),
  detail: (id: number) => get<SalaryDetail>(`/salaries/${id}`),
  generate: (data: { year_month: string; user_ids?: number[] }) =>
    post<GenerateResult>('/salaries/generate', data),
  confirm: (id: number) => put<SalaryItem>(`/salaries/${id}/confirm`),
  pay: (id: number) => put<SalaryItem>(`/salaries/${id}/pay`),
  adjustments: (params: { year_month?: string; user_id?: number; page: number; page_size: number }) =>
    get<PageResult<AdjustmentItem>>('/salaries/adjustments', { params }),
  createAdjustment: (data: {
    user_id: number
    adjust_type: number
    amount: number
    reason: string
    year_month?: string
  }) => post<AdjustmentItem>('/salaries/adjustments', data),
}
