/* @vitest-environment jsdom */
import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import MessageItem from './MessageItem'
import type { ChatMsg } from './useChat'

// jsdom 未实现 matchMedia，antd 部分组件依赖它
if (!window.matchMedia) {
  window.matchMedia = ((query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList)
}

afterEach(cleanup)

const wrap = (node: React.ReactNode) => <BrowserRouter>{node}</BrowserRouter>

describe('MessageItem 对话体验增强', () => {
  it('流式中思考面板默认展开（思考内容可见），结束后自动收起且标题含思考时长', () => {
    const reasoning = '先检索考勤制度…'
    const streamingMsg: ChatMsg = {
      role: 'assistant',
      content: '正在回答',
      reasoning,
      streaming: true,
    }
    const { container, rerender } = render(wrap(<MessageItem msg={streamingMsg} />))
    const header = () => container.querySelector('.ant-collapse-header')
    // 流式中展开：面板 aria-expanded=true 且思考内容在 DOM
    expect(header()?.getAttribute('aria-expanded')).toBe('true')
    expect(container.textContent).toContain(reasoning)

    const doneMsg: ChatMsg = { ...streamingMsg, streaming: false, reasoningSeconds: 3.2 }
    rerender(wrap(<MessageItem msg={doneMsg} />))
    // 结束后自动收起：面板 aria-expanded=false，标题行带时长
    expect(header()?.getAttribute('aria-expanded')).toBe('false')
    expect(container.textContent).toContain('思考过程 · 3.2s')
  })

  it('历史消息（非流式）思考面板默认收起，可手动展开', () => {
    const reasoning = '历史思考内容'
    const { queryByText } = render(
      wrap(<MessageItem msg={{ role: 'assistant', content: '答案', reasoning }} />),
    )
    expect(queryByText(reasoning)).toBeNull()
    expect(queryByText('思考过程')).toBeTruthy()
  })

  it('错误消息渲染红框错误信息与重试按钮，点击触发 onRetry', () => {
    const onRetry = vi.fn()
    const { getByText } = render(
      wrap(
        <MessageItem
          msg={{
            role: 'assistant',
            content: '',
            error: true,
            errorText: '余额不足或无可用资源包',
          }}
          showRetry
          onRetry={onRetry}
        />,
      ),
    )
    expect(getByText(/余额不足或无可用资源包/)).toBeTruthy()
    fireEvent.click(getByText('重试'))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('用户停止（非错误）不渲染错误文案', () => {
    const { queryByText } = render(
      wrap(<MessageItem msg={{ role: 'assistant', content: '', stopped: true }} />),
    )
    expect(queryByText(/生成失败/)).toBeNull()
    expect(queryByText('已停止生成')).toBeTruthy()
  })
})
