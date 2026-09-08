import { describe, expect, it } from 'vitest'
import { parseSSEBlock } from './sse'

describe('parseSSEBlock', () => {
  it('解析 event + data', () => {
    expect(parseSSEBlock('event: message\ndata: {"a":1}')).toEqual({
      event: 'message',
      data: '{"a":1}',
    })
  })

  it('无 event 行时缺省为 message', () => {
    expect(parseSSEBlock('data: hello')).toEqual({ event: 'message', data: 'hello' })
  })

  it('多条 data 行按换行拼接', () => {
    expect(parseSSEBlock('event: meta\ndata: line1\ndata: line2')).toEqual({
      event: 'meta',
      data: 'line1\nline2',
    })
  })

  it('data 值去除前缀后 trim', () => {
    expect(parseSSEBlock('data:   padded   ')).toEqual({ event: 'message', data: 'padded' })
  })

  it('无 data 行的块返回 null', () => {
    expect(parseSSEBlock('event: ping')).toBeNull()
    expect(parseSSEBlock('')).toBeNull()
    expect(parseSSEBlock('注释行')).toBeNull()
  })
})
