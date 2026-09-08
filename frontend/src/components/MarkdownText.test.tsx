/* @vitest-environment jsdom */
import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import MarkdownText from './MarkdownText'

afterEach(cleanup)

describe('MarkdownText 代码块增强', () => {
  it('渲染语言标签与复制按钮', () => {
    const { container } = render(
      <MarkdownText content={'```python\nprint("hi")\n```'} />,
    )
    expect(container.querySelector('.md-code-language')?.textContent).toBe('python')
    expect(container.querySelector('.md-code-copy')?.textContent).toContain('复制')
    expect(container.querySelector('.md-code-pre code.language-python')).toBeTruthy()
  })

  it('无语言代码块缺省显示 code 标签', () => {
    const { container } = render(<MarkdownText content={'```\nplain text\n```'} />)
    expect(container.querySelector('.md-code-language')?.textContent).toBe('code')
  })

  it('python 代码经 highlight.js 产出 token 着色', () => {
    const { container } = render(
      <MarkdownText content={'```python\ndef add(a, b):\n    return a + b\n```'} />,
    )
    const highlighted = container.querySelector('.md-code-pre code')?.innerHTML ?? ''
    expect(highlighted).toContain('hljs-keyword')
    // 原文仍保留且被转义，未被误吞
    expect(highlighted).toContain('def')
  })

  it('普通段落不触发代码块外壳', () => {
    const { container } = render(<MarkdownText content={'只是一段普通文本'} />)
    expect(container.querySelector('.md-code-block')).toBeNull()
  })
})
