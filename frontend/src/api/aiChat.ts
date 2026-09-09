import type { PageResult } from '@/types'
import { del, get, patch } from './request'
import type { Citation } from './kb'
import { fetchSSE } from './sse'

export interface AIConversationItem {
  id: number
  title: string | null
  /** 置顶状态：置顶会话在列表中优先展示 */
  pinned: boolean
  created_at: string
  updated_at: string
}

export interface AIMessageItem {
  id: number
  role: 'user' | 'assistant' | 'tool'
  content: string
  reasoning_content: string | null
  tool_name: string | null
  citations: Citation[] | null
  attachments: { type: string; url: string }[] | null
  usage: { total_tokens?: number; model?: string } | null
  created_at: string
}

export interface AIConversationDetail extends AIConversationItem {
  messages: AIMessageItem[]
  message_total: number
  has_more: boolean
  /** 上下文容量估算（后端与真实请求同口径：最近4轮+系统提示词+工具定义+工具结果，不含记忆注入） */
  context_usage?: { total: number; breakdown: { label: string; tokens: number }[] }
}

/** 本人长期记忆条目 */
export interface AIMemoryItem {
  id: number
  content: string
  memory_type: string
  source_conversation_id: number | null
  created_at: string
  updated_at: string
}

export interface AIToolEvent {
  tool: 'retrieve' | 'nl2sql' | 'server_admin' | string
  query?: string
  question?: string
  /** server_admin 工具的探查动作与路径 */
  action?: string
  path?: string
}

/** 本轮问答用量统计（usage 为上游未回传时的估算值，estimated=true） */
export interface AIChatStats {
  duration_ms: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated: boolean
  context_tokens: number
  context_window: number
  context_breakdown: { label: string; tokens: number }[]
}

/** 上下文容量展示数据（输入区圆环悬停浮层用） */
export interface ContextUsage {
  used: number
  total: number
  breakdown: { label: string; tokens: number }[]
  /** 缓存命中率（0-1）；上游不支持时为 null，前端隐藏对应行 */
  cacheHitRate: number | null
}

/** 启用中的生成模型（模型切换下拉项） */
export interface AIModelOption {
  id: number
  name: string
  model_name: string
  is_default: boolean
  context_window?: number
}

/** 长期记忆召回事件 */
export interface AIMemoryEvent {
  count: number
  items: { id: number; type: string; content: string }[]
}

export interface AIChatStreamHandlers {
  /** 会话元信息：conversation_id（新会话在此产生） */
  onMeta?: (data: { conversation_id: number }) => void
  /** 工具调用事件（检索/查询产品数据） */
  onTool?: (data: AIToolEvent) => void
  /** 正文增量 */
  onMessage?: (delta: string) => void
  /** 推理增量（开启深度思考才有） */
  onReasoning?: (delta: string) => void
  /** 引用来源列表 */
  onCitations?: (citations: Citation[]) => void
  /** 长期记忆召回（本轮注入 system prompt 的记忆条数与内容摘要） */
  onMemory?: (data: AIMemoryEvent) => void
  /** 生成结束（附用量统计） */
  onDone?: (data: {
    conversation_id: number
    message_id: number
    usage?: Omit<AIChatStats, 'duration_ms' | 'context_breakdown'>
    duration_ms?: number
    context_tokens?: number
    context_window?: number
    context_breakdown?: { label: string; tokens: number }[]
    cache_hit_rate?: number
    memory_count?: number
  }) => void
  /** 服务端下发的 error 事件 */
  onError?: (message: string) => void
}

export const aiChatApi = {
  conversations: (params: { page?: number; page_size?: number; source?: string }) =>
    get<PageResult<AIConversationItem>>('/ai/conversations', { params }),
  conversation: (id: number) => get<AIConversationDetail>(`/ai/conversations/${id}`),
  removeConversation: (id: number) => del(`/ai/conversations/${id}`),
  /** 启用中的生成模型列表（模型切换下拉） */
  models: () => get<AIModelOption[]>('/ai/enabled-models'),
  /** 会话更早消息分页 */
  listMessages: (conversationId: number, beforeId: number, limit = 100) =>
    get<{ messages: AIMessageItem[]; has_more: boolean }>(
      `/ai/conversations/${conversationId}/messages`, { params: { before_id: beforeId, limit } },
    ),
  /** 本人用量汇总（成本监控） */
  usageSummary: (days = 30) =>
    get<{
      requests: number
      prompt_tokens: number
      completion_tokens: number
      total_tokens: number
      by_day: { date: string; tokens: number }[]
      by_model: { model: string; tokens: number }[]
    }>('/ai/usage/summary', { params: { days } }),
  /** 长期记忆管理 */
  memories: (params: { page?: number; page_size?: number }) =>
    get<PageResult<AIMemoryItem>>('/ai/memories', { params }),
  updateMemory: (id: number, content: string) => patch<AIMemoryItem>(`/ai/memories/${id}`, { content }),
  deleteMemory: (id: number) => del(`/ai/memories/${id}`),
  clearMemories: () => del('/ai/memories'),
  /** 会话重命名 */
  rename: (id: number, title: string) =>
    patch<AIConversationItem>(`/ai/conversations/${id}`, { title }),
  /** 会话置顶切换 */
  setPinned: (id: number, pinned: boolean) =>
    patch<AIConversationItem>(`/ai/conversations/${id}`, { pinned }),
}

/**
 * AI助手 SSE 流：事件序列 meta→tool*→[reasoning*]→message*→[citations]→done。
 * 底层 fetch/401 刷新/流式解析收敛在 ./sse 公共基座，此处仅做事件映射。
 */
export async function streamAIChat(
  payload: {
    question: string
    conversation_id?: number | null
    deep_thinking?: boolean
    images?: string[]
    model_id?: number
    kb_ids?: number[]
    source?: 'ai' | 'kb'
  },
  handlers: AIChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await fetchSSE(
    '/api/v1/ai/chat',
    payload,
    {
      onEvent: (event, data) => {
        switch (event) {
          case 'meta':
            handlers.onMeta?.({ conversation_id: Number(data.conversation_id) })
            break
          case 'tool':
            handlers.onTool?.({
              tool: String(data.tool ?? ''),
              query: data.query != null ? String(data.query) : undefined,
              question: data.question != null ? String(data.question) : undefined,
              action: data.action != null ? String(data.action) : undefined,
              path: data.path != null ? String(data.path) : undefined,
            })
            break
          case 'message':
            handlers.onMessage?.(String(data.delta ?? ''))
            break
          case 'reasoning':
            handlers.onReasoning?.(String(data.delta ?? ''))
            break
          case 'citations':
            handlers.onCitations?.(data as unknown as Citation[])
            break
          case 'memory':
            handlers.onMemory?.({
              count: Number(data.count ?? 0),
              items: Array.isArray(data.items) ? data.items : [],
            })
            break
          case 'done':
            handlers.onDone?.({
              conversation_id: Number(data.conversation_id),
              message_id: Number(data.message_id),
              usage: data.usage as Omit<AIChatStats, 'duration_ms' | 'context_breakdown'> | undefined,
              duration_ms: data.duration_ms != null ? Number(data.duration_ms) : undefined,
              context_tokens: data.context_tokens != null ? Number(data.context_tokens) : undefined,
              context_window: data.context_window != null ? Number(data.context_window) : undefined,
              context_breakdown: Array.isArray(data.context_breakdown) ? data.context_breakdown : undefined,
              cache_hit_rate: data.cache_hit_rate != null ? Number(data.cache_hit_rate) : undefined,
              memory_count: data.memory_count != null ? Number(data.memory_count) : undefined,
            })
            break
          case 'error':
            handlers.onError?.(String(data.message ?? '生成失败'))
            break
        }
      },
      onError: (msg) => handlers.onError?.(msg),
    },
    signal,
  )
}
