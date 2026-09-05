import type { PageResult } from '@/types'
import { get } from './request'

export interface LogItem {
  id: number
  username: string | null
  module: string | null
  action: string | null
  method: string | null
  path: string | null
  params: string | null
  ip: string | null
  result: number
  error_message: string | null
  duration_ms: number
  created_at: string
}

export interface LogListParams {
  keyword?: string
  module?: string
  result?: number
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export const logApi = {
  list: (params: LogListParams) => get<PageResult<LogItem>>('/logs', { params }),
}
