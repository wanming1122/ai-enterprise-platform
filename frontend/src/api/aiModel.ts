import { del, get, post, put } from '@/api/request'
import type { PageResult } from '@/types'

/** 模型配置（列表项）：api_key 仅返回掩码 */
export interface AIModelItem {
  id: number
  name: string
  model_type: 'llm' | 'embedding' | 'rerank'
  model_type_label: string
  provider: 'zhipu' | 'dashscope' | 'openai_compatible' | 'local'
  provider_label: string
  base_url: string | null
  api_key_masked: string
  model_name: string
  temperature: number | null
  /** 上下文窗口（token，仅 llm；空则后端回退全局常量） */
  context_window: number | null
  remark: string | null
  is_default: boolean
  status: number
  status_label: string
  created_at: string | null
}

export interface AIModelSavePayload {
  name: string
  model_type: AIModelItem['model_type']
  provider: AIModelItem['provider']
  base_url?: string
  /** 编辑时留空表示保持原密钥 */
  api_key?: string
  model_name: string
  temperature?: number | null
  context_window?: number | null
  remark?: string
  is_default?: boolean
  status?: number
}

/** 连通性测试结果 */
export interface ModelTestResult {
  latency_ms: number
  detail: string
}

export const aiModelApi = {
  /** 模型配置分页列表 */
  list: (params: { model_type?: string; keyword?: string; page?: number; page_size?: number }) =>
    get<PageResult<AIModelItem>>('/ai/models', { params }),
  /** 新增模型配置 */
  create: (data: AIModelSavePayload) => post<AIModelItem>('/ai/models', data),
  /** 编辑模型配置（api_key 留空保持原值） */
  update: (id: number, data: AIModelSavePayload) => put<AIModelItem>(`/ai/models/${id}`, data),
  /** 软删除模型配置 */
  remove: (id: number) => del(`/ai/models/${id}`),
  /** 设为同类型唯一默认 */
  setDefault: (id: number) => post<AIModelItem>(`/ai/models/${id}/default`),
  /** 连通性测试 */
  test: (id: number) => post<ModelTestResult>(`/ai/models/${id}/test`),
}

export const MODEL_TYPE_OPTIONS = [
  { value: 'llm', label: '生成模型' },
  { value: 'embedding', label: '向量模型' },
  { value: 'rerank', label: '重排模型' },
]

export const PROVIDER_OPTIONS = [
  { value: 'zhipu', label: '智谱' },
  { value: 'dashscope', label: '通义百炼' },
  { value: 'openai_compatible', label: 'OpenAI兼容' },
  { value: 'local', label: '本地部署' },
]

/** 服务商缺省接口地址提示（与后端 DEFAULT_BASE_URL 对应） */
export const PROVIDER_BASE_URL_HINT: Record<string, string> = {
  zhipu: '留空使用智谱默认：https://open.bigmodel.cn/api/paas/v4',
  dashscope: '留空使用通义默认：https://dashscope.aliyuncs.com/compatible-mode/v1',
  openai_compatible: 'OpenAI 兼容服务必须填写接口地址',
  local: '本地部署服务必须填写接口地址',
}
