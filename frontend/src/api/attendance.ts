import { downloadBlob, get, post, put } from '@/api/request'
import type { PageResult } from '@/types'

/** 考勤记录项 */
export interface AttRecordItem {
  id: number
  user_id: number
  username?: string
  real_name?: string | null
  dept_id?: number | null
  dept_name?: string | null
  att_date: string
  check_in?: string | null
  check_out?: string | null
  status: string
  status_label: string
  location?: string | null
  remark?: string | null
  source: number
  source_label: string
  created_at?: string | null
}

/** 手动补录表单 */
export interface AttRecordForm {
  user_id?: number
  att_date?: string
  check_in?: string | null
  check_out?: string | null
  status?: string
  location?: string
  remark?: string
}

/** 导入结果 */
export interface AttImportResult {
  total: number
  success: number
  failed: number
  overwritten: number
  errors: { row: number; reason: string }[]
}

/** 考勤规则项 */
export interface AttRuleItem {
  id: number
  status_key: string
  status_label: string
  adjust_type: number
  amount: string
  enabled: number
  updated_at?: string | null
}

/** 考勤状态选项（与后端考勤状态字典一致） */
export const ATT_STATUS_OPTIONS: { value: string; label: string; color: string }[] = [
  { value: 'normal', label: '正常', color: 'green' },
  { value: 'late', label: '迟到', color: 'orange' },
  { value: 'early_leave', label: '早退', color: 'orange' },
  { value: 'miss_check', label: '漏签', color: 'gold' },
  { value: 'absent', label: '旷工', color: 'red' },
  { value: 'leave', label: '请假', color: 'blue' },
  { value: 'business_trip', label: '出差', color: 'cyan' },
]

export const attApi = {
  list: (params: {
    department_id?: number
    user_id?: number
    month?: string
    status?: string
    page: number
    page_size: number
  }) => get<PageResult<AttRecordItem>>('/attendances', { params }),
  create: (data: AttRecordForm) => post<{ id: number; overwritten: boolean }>('/attendances', data),
  importRecords: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return post<AttImportResult>('/attendances/import', form)
  },
  downloadTemplate: () => downloadBlob('/attendances/template'),
  rules: () => get<AttRuleItem[]>('/attendance-rules'),
  updateRule: (id: number, data: { adjust_type?: number; amount?: number; enabled?: number }) =>
    put<AttRuleItem>(`/attendance-rules/${id}`, data),
}
