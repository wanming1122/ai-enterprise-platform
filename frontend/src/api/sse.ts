/**
 * SSE 流式公共基座（AI 助手与知识库问答复用）。
 *
 * axios 实例有 15s 超时且经统一拦截器，不适合长流式，两个聊天接口均使用原生
 * fetch + ReadableStream 手工解析事件流。此文件收敛两处的公共实现：
 * - 携带 Bearer 发起 POST、401 复用全局刷新令牌重放一次（失败清 token 跳登录并抛错）
 * - 非 2xx / 无 body 时按统一响应结构解析 message 回调 onError（不抛出）
 * - 按空行切块、逐块解析为 (event, JSON data)，交由调用方分发
 */
import { clearTokens, getAccessToken, refreshAccessToken } from './request'

/** 解析单个 SSE 事件块（event: xxx + data: xxx，缺省 event 为 message） */
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

export interface FetchSSEHandlers {
  /** 逐事件分派：data 为已 JSON.parse 的对象（parse 失败的事件被静默忽略） */
  onEvent: (event: string, data: Record<string, unknown>) => void
  /** HTTP 层错误（403 无权限 / 422 参数问题等）：按统一响应结构回调提示 */
  onError?: (message: string) => void
}

/**
 * 发起一次 SSE POST 流式请求并持续读取到结束。
 * 返回时流已正常读完（含服务端 error 事件）；401 刷新失败会抛出登录过期错误，
 * AbortSignal 中止时向上抛 AbortError，由调用方按既有语义处理。
 */
export async function fetchSSE(
  url: string,
  payload: unknown,
  handlers: FetchSSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const doFetch = (token: string) =>
    fetch(url, {
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
    handlers.onEvent(parsed.event, data)
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
