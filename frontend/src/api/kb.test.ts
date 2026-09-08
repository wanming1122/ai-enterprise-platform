import { beforeEach, describe, expect, it, vi } from 'vitest'

// kb.ts 以 re-export 形式暴露 parseSSEBlock，mock 工厂需保留该导出以免解析失败
vi.mock('./sse', () => ({ fetchSSE: vi.fn(), parseSSEBlock: vi.fn() }))

import { fetchSSE } from './sse'
import { streamKBChat, type ChatStreamHandlers } from './kb'

const mockedFetchSSE = vi.mocked(fetchSSE)

describe('streamKBChat 事件映射', () => {
  beforeEach(() => {
    mockedFetchSSE.mockReset()
  })

  it('meta/message/reasoning/done 事件映射（含 search_query 与 references_used 字段）', async () => {
    const order: string[] = []
    mockedFetchSSE.mockImplementation(async (_url, _payload, handlers) => {
      handlers.onEvent('meta', { conversation_id: 5, search_query: '年假' })
      handlers.onEvent('reasoning', { delta: '检索中' })
      handlers.onEvent('message', { delta: '根据制度' })
      handlers.onEvent('done', { conversation_id: 5, message_id: 7, references_used: 3 })
    })

    const handlers: ChatStreamHandlers = {
      onMeta: (d) => order.push(`meta:${d.conversation_id}:${d.search_query}`),
      onReasoning: (d) => order.push(`r:${d}`),
      onMessage: (d) => order.push(`msg:${d}`),
      onDone: (d) => order.push(`done:${d.message_id}:ref${d.references_used}`),
    }
    await streamKBChat({ question: '年假几天', kb_ids: [1] }, handlers)

    expect(order).toEqual(['meta:5:年假', 'r:检索中', 'msg:根据制度', 'done:7:ref3'])
  })

  it('citations 与 error 事件正确回传', async () => {
    const got: string[] = []
    mockedFetchSSE.mockImplementation(async (_url, _payload, handlers) => {
      // citations 的 SSE data 本身即数组（运行时原样透传），这里模拟真实载荷
      handlers.onEvent(
        'citations',
        [{ index: 2, file_name: '考勤.md', snippet: 'x' }] as unknown as Record<string, unknown>,
      )
      handlers.onEvent('error', { message: '超时' })
    })

    await streamKBChat(
      { question: 'q', kb_ids: [1] },
      {
        onCitations: (c) => got.push(`c:${c[0]?.index}:${c[0]?.file_name}`),
        onError: (m) => got.push(`e:${m}`),
      },
    )
    expect(got).toEqual(['c:2:考勤.md', 'e:超时'])
  })
})
