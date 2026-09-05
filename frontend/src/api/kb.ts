import { clearTokens, del, get, getAccessToken, post, put, refreshAccessToken } from '@/api/request'
import type { PageResult } from '@/types'

/** 知识库（列表/详情） */
export interface KBBase {
  id: number
  name: string
  description: string | null
  embedding_model: string
  embedding_dimension: number
  chunk_size: number
  chunk_overlap: number
  collection_name: string
  status: number
  file_count: number
  chunk_count: number
  created_at: string | null
}

/** 知识库文件（parse_status：0待解析 1解析中 2已入库 3失败） */
export interface KBFileItem {
  id: number
  kb_id: number
  file_name: string
  file_type: string
  file_size: number
  chunk_count: number
  parse_status: number
  parse_status_label: string
  fail_reason: string | null
  status: number
  created_at: string | null
}

/** 切片预览项 */
export interface KBChunkItem {
  id: number
  chunk_index: number
  content: string
  char_count: number | null
  title_path: string | null
  page: number | null
  chunk_type: string
}

/** 问答引用来源（citations 事件元素 / 历史消息内嵌） */
export interface Citation {
  index: number
  file_name: string | null
  title_path: string | null
  page: number | null
  similarity: number | null
  snippet: string
}

/** 检索调试命中切片 */
export interface SearchHit {
  kb_id: number
  kb_name: string
  file_id: number | null
  file_name: string
  chunk_index: number | null
  content: string
  title_path: string | null
  page: number | null
  chunk_type: string
  similarity: number
}

/** 问答会话 */
export interface ConversationItem {
  id: number
  title: string
  created_at: string
  updated_at: string
}

/** 会话历史详情 */
export interface ConversationDetail {
  id: number
  title: string
  created_at: string
  messages: {
    id: number
    role: 'user' | 'assistant' | 'tool'
    content: string
    citations: Citation[]
    created_at: string
  }[]
}

export interface KBQuery {
  keyword?: string
  page?: number
  page_size?: number
}

export const kbApi = {
  /** 知识库分页列表 */
  list: (params: KBQuery) => get<PageResult<KBBase>>('/kb/bases', { params }),
  /** 新建知识库（embedding_dimension 缺省时后端自动探测） */
  create: (data: { name: string; description?: string; chunk_size?: number; chunk_overlap?: number }) =>
    post<KBBase>('/kb/bases', data),
  /** 编辑知识库（模型与维度不可改） */
  update: (id: number, data: { name?: string; description?: string; chunk_size?: number; chunk_overlap?: number }) =>
    put<KBBase>(`/kb/bases/${id}`, data),
  /** 软删除知识库及其下全部文件 */
  remove: (id: number) => del(`/kb/bases/${id}`),
  /** 重建向量索引，返回 {kb_id, chunks} */
  rebuild: (id: number) => post<{ kb_id: number; chunks: number }>(`/kb/bases/${id}/rebuild`),

  /** 上传文件（multipart），落盘后异步解析 */
  upload: (kbId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return post<KBFileItem>(`/kb/bases/${kbId}/files`, form)
  },
  /** 库内文件分页列表 */
  files: (
    kbId: number,
    params: { parse_status?: number; page?: number; page_size?: number },
  ) => get<PageResult<KBFileItem>>(`/kb/bases/${kbId}/files`, { params }),
  /** 切片分页预览 */
  chunks: (fileId: number, params: { page?: number; page_size?: number }) =>
    get<PageResult<KBChunkItem>>(`/kb/files/${fileId}/chunks`, { params }),
  /** 软删除文件 */
  removeFile: (fileId: number) => del(`/kb/files/${fileId}`),
  /** 重新解析（清空原切片后重跑） */
  reparseFile: (fileId: number) => post(`/kb/files/${fileId}/reparse`),

  /** 检索调试：返回命中切片与相似度 */
  search: (data: { query: string; kb_ids: number[]; top_k?: number }) =>
    post<SearchHit[]>('/kb/search', data),
  /** 我的问答会话列表 */
  conversations: (params: { page?: number; page_size?: number }) =>
    get<PageResult<ConversationItem>>('/kb/conversations', { params }),
  /** 会话历史（仅本人） */
  conversation: (id: number) => get<ConversationDetail>(`/kb/conversations/${id}`),
}

export interface ChatStreamHandlers {
  /** 会话元信息：conversation_id（新会话在此产生）与本轮检索改写词 */
  onMeta?: (data: { conversation_id: number; search_query: string }) => void
  /** 正文增量 */
  onMessage?: (delta: string) => void
  /** 推理增量（推理模型才有） */
  onReasoning?: (delta: string) => void
  /** 引用来源列表 */
  onCitations?: (citations: Citation[]) => void
  /** 生成结束 */
  onDone?: (data: { conversation_id: number; message_id: number; references_used: number }) => void
  /** 服务端下发的 error 事件 */
  onError?: (message: string) => void
}

/** 解析单个 SSE 事件块（event: xxx + data: xxx）；AI助手流式接口复用 */
export function parseSSEBlock(block: string): { event: string; data: string } | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return null
  return { event, data: dataLines.join('\n') }
}

function dispatchSSE(event: string, raw: string, handlers: ChatStreamHandlers): void {
  let data: Record<string, unknown>
  try {
    data = JSON.parse(raw) as Record<string, unknown>
  } catch {
    return
  }
  switch (event) {
    case 'meta':
      handlers.onMeta?.({ conversation_id: Number(data.conversation_id), search_query: String(data.search_query ?? '') })
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
        references_used: Number(data.references_used ?? 0),
      })
      break
    case 'error':
      handlers.onError?.(String(data.message ?? '生成失败'))
      break
  }
}

/**
 * 知识库问答 SSE 流：axios 实例有 15s 超时且经统一拦截器，不适合长流式，
 * 这里用原生 fetch + ReadableStream 手工解析事件流（meta→message*→[reasoning*]→citations→done）。
 * 401 时复用全局刷新令牌逻辑重放一次，刷新失败跳登录页。
 */
export async function streamKBChat(
  payload: { question: string; kb_ids: number[]; conversation_id?: number | null; top_k?: number },
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const doFetch = (token: string) =>
    fetch('/api/v1/kb/chat', {
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
    // HTTP 层错误（403 无权限 / 422 参数问题等）：按统一响应结构回调提示，不再抛出
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
    if (parsed) dispatchSSE(parsed.event, parsed.data, handlers)
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 事件以空行分隔；末尾不足一个完整事件时留在缓冲区
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    blocks.forEach(handle)
  }
  if (buffer.trim()) handle(buffer)
}
