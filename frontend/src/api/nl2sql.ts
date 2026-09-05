import type { PageResult } from '@/types'
import { get, post } from './request'

/** 执行结果：columns 取自首行键序，rows 值均已转为字符串 */
export interface NL2SQLResult {
  columns: string[]
  rows: Record<string, string | number | null>[]
}

export interface NL2SQLRecordItem {
  id: number
  username: string | null
  question: string
  generated_sql: string
  review_status: 0 | 1 | 2 | 3
  review_status_label: string
  review_comment: string | null
  reviewer_id: number | null
  result_count: number | null
  execution_ms: number | null
  executed_at: string | null
  created_at: string
  /** 仅详情/执行响应携带完整结果 */
  result?: NL2SQLResult
}

export type ReviewAction = 'approve' | 'reject'

export interface NL2SQLListParams {
  keyword?: string
  status?: number
  page?: number
  page_size?: number
}

export const REVIEW_STATUS_OPTIONS = [
  { value: 0, label: '待审核' },
  { value: 1, label: '通过' },
  { value: 2, label: '驳回' },
  { value: 3, label: '已执行' },
]

export const REVIEW_STATUS_COLOR: Record<number, string> = {
  0: 'warning',
  1: 'processing',
  2: 'error',
  3: 'success',
}

export const nl2sqlApi = {
  /** 生成 SQL：推理模型可能较慢，单独放宽超时 */
  generate: (question: string) =>
    post<NL2SQLRecordItem>('/nl2sql/generate', { question }, { timeout: 120000 }),
  records: (params: NL2SQLListParams) => get<PageResult<NL2SQLRecordItem>>('/nl2sql/records', { params }),
  history: (params: NL2SQLListParams) => get<PageResult<NL2SQLRecordItem>>('/nl2sql/history', { params }),
  detail: (id: number) => get<NL2SQLRecordItem>(`/nl2sql/records/${id}`),
  review: (id: number, action: ReviewAction, comment?: string) =>
    post<NL2SQLRecordItem>(`/nl2sql/records/${id}/review`, { action, comment: comment || undefined }),
  execute: (id: number) =>
    post<NL2SQLRecordItem>(`/nl2sql/records/${id}/execute`, undefined, { timeout: 30000 }),
}
