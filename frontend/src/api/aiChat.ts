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
  created_at: string
}

export interface AIConversationDetail extends AIConversationItem {
  messages: AIMessageItem[]
}

export interface AIToolEvent {
  tool: 'retrieve' | 'nl2sql' | 'server_admin' | string
  query?: string
  question?: string
  /** server_admin 工具的探查动作与路径 */
  action?: string
  path?: string
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
  /** 生成结束 */
  onDone?: (data: { conversation_id: number; message_id: number }) => void
  /** 服务端下发的 error 事件 */
  onError?: (message: string) => void
}

export const aiChatApi = {
  conversations: (params: { page?: number; page_size?: number }) =>
    get<PageResult<AIConversationItem>>('/ai/conversations', { params }),
  conversation: (id: number) => get<AIConversationDetail>(`/ai/conversations/${id}`),
  removeConversation: (id: number) => del(`/ai/conversations/${id}`),
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
  payload: { question: string; conversation_id?: number | null; deep_thinking?: boolean; images?: string[] },
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
          case 'done':
            handlers.onDone?.({
              conversation_id: Number(data.conversation_id),
              message_id: Number(data.message_id),
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
