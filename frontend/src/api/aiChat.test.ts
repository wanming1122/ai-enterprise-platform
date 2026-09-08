import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./sse', () => ({ fetchSSE: vi.fn() }))

import { fetchSSE } from './sse'
import { streamAIChat, type AIChatStreamHandlers } from './aiChat'

const mockedFetchSSE = vi.mocked(fetchSSE)

describe('streamAIChat 事件映射', () => {
  beforeEach(() => {
    mockedFetchSSE.mockReset()
  })

  it('meta/tool/message/done 事件按序映射到对应 handlers', async () => {
    const order: string[] = []
    mockedFetchSSE.mockImplementation(async (_url, _payload, handlers) => {
      handlers.onEvent('meta', { conversation_id: 3 })
      handlers.onEvent('tool', { tool: 'nl2sql', question: '库存多少' })
      handlers.onEvent('message', { delta: '当前' })
      handlers.onEvent('done', { conversation_id: 3, message_id: 9 })
    })

    const handlers: AIChatStreamHandlers = {
      onMeta: (d) => order.push(`meta:${d.conversation_id}`),
      onTool: (t) => order.push(`tool:${t.tool}:${t.question}`),
      onMessage: (d) => order.push(`msg:${d}`),
      onDone: (d) => order.push(`done:${d.conversation_id}:${d.message_id}`),
    }
    await streamAIChat({ question: 'q' }, handlers)

    expect(order).toEqual(['meta:3', 'tool:nl2sql:库存多少', 'msg:当前', 'done:3:9'])
  })

  it('reasoning/citations 事件正确回传', async () => {
    const got: string[] = []
    mockedFetchSSE.mockImplementation(async (_url, _payload, handlers) => {
      handlers.onEvent('reasoning', { delta: '思考中' })
      // citations 的 SSE data 本身即数组（运行时原样透传），这里模拟真实载荷
      handlers.onEvent(
        'citations',
        [{ index: 1, file_name: '制度.md', snippet: '片段' }] as unknown as Record<string, unknown>,
      )
    })

    await streamAIChat(
      { question: 'q', deep_thinking: true },
      {
        onReasoning: (d) => got.push(`r:${d}`),
        onCitations: (c) => got.push(`c:${c[0]?.index}:${c[0]?.file_name}`),
      },
    )

    expect(got).toEqual(['r:思考中', 'c:1:制度.md'])
  })

  it('服务端 error 事件与 HTTP onError 均回传给 onError', async () => {
    const errors: string[] = []
    mockedFetchSSE.mockImplementation(async (_url, _payload, handlers) => {
      handlers.onEvent('error', { message: '服务端生成失败' })
      handlers.onError?.('请求失败（HTTP 403）')
    })

    await streamAIChat({ question: 'q' }, { onError: (m) => errors.push(m) })
    expect(errors).toEqual(['服务端生成失败', '请求失败（HTTP 403）'])
  })
})
