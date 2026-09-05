import type { PageResult } from '@/types'
import { get, del } from './request'
import { getAccessToken, clearTokens, refreshAccessToken } from './request'
import { parseSSEBlock, type Citation } from './kb'

export interface AIConversationItem {
  id: number
  title: string | null
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
  created_at: string
}

export interface AIConversationDetail extends AIConversationItem {
  messages: AIMessageItem[]
}

export interface AIToolEvent {
  tool: 'retrieve' | 'nl2sql' | string
  query?: string
  question?: string
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
}

/**
 * AI助手 SSE 流：原生 fetch + ReadableStream 手工解析（与 streamKBChat 同协议，
 * 事件序列 meta→tool*→[reasoning*]→message*→[citations]→done）。401 复用全局刷新令牌重放。
 */
export async function streamAIChat(
  payload: { question: string; conversation_id?: number | null; deep_thinking?: boolean },
  handlers: AIChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const doFetch = (token: string) =>
    fetch('/api/v1/ai/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
      signal,
    })

  let res = await doFetch(getAccessToken() ?? '')
  if (res.status === 401) {
    try {
      res = await doFetch(await refreshAccessToken())
    } catch {
      clearTokens()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
      throw new Error('登录已过期，请重新登录')
    }
  }

  if (!res.ok || !res.body) {
    let msg = `请求失败（HTTP ${res.status}）`
    try {
      const body = (await res.json()) as { message?: string }
      if (body?.message) msg = body.message
    } catch {
      // 保留默认文案
    }
    handlers.onError?.(msg)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  const handle = (block: string) => {
    const parsed = parseSSEBlock(block)
    if (!parsed) return
    let data: Record<string, unknown>
    try {
      data = JSON.parse(parsed.data) as Record<string, unknown>
    } catch {
      return
    }
    switch (parsed.event) {
      case 'meta':
        handlers.onMeta?.({ conversation_id: Number(data.conversation_id) })
        break
      case 'tool':
        handlers.onTool?.({
          tool: String(data.tool ?? ''),
          query: data.query != null ? String(data.query) : undefined,
          question: data.question != null ? String(data.question) : undefined,
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
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    blocks.forEach(handle)
  }
  if (buffer.trim()) handle(buffer)
}
