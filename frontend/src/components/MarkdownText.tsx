/**
 * AI 回复正文的 Markdown 渲染：支持 GFM（表格/删除线/任务列表）、链接新开页。
 * 代码块增强：语言标签 + 一键复制 + highlight.js 语法高亮 + 最高 400px 内部滚动。
 * 高亮配色映射到 antd cssVar（--ant-*），明暗主题自动适配。
 */
import { isValidElement, useMemo, useState, type ReactElement } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import hljs from 'highlight.js/lib/common'
import { CheckOutlined, CopyOutlined } from '@ant-design/icons'
import './MarkdownText.css'

/** 原样转义代码文本：无匹配语言时不走 highlightAuto，避免把普通文本误当代码高亮 */
function escapeHtml(code: string): string {
  return code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 代码块：语言标签 + 复制 + 高亮渲染 */
function CodeBlock({ code, language }: { code: string; language?: string }) {
  const lang = language && hljs.getLanguage(language) ? language : null
  const html = useMemo(
    () => (lang ? hljs.highlight(code, { language: lang }).value : escapeHtml(code)),
    [code, lang],
  )
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // 剪贴板不可用时静默忽略
    }
  }

  return (
    <div className="md-code-block">
      <div className="md-code-block-header">
        <span className="md-code-language">{language || 'code'}</span>
        <button type="button" className="md-code-copy" onClick={handleCopy} title="复制代码">
          {copied ? <CheckOutlined /> : <CopyOutlined />}
          <span>{copied ? '已复制' : '复制'}</span>
        </button>
      </div>
      <pre className="md-code-pre">
        {/* hljs 输出前已对原文转义，仅追加语法 span，可安全注入 */}
        <code
          className={`hljs${lang ? ` language-${lang}` : ''}`}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </pre>
    </div>
  )
}

export default function MarkdownText({ content }: { content: string }) {
  return (
    <div className="md-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
          // 围栏代码块：从 <pre> 的子 <code> 上提取语言与文本，渲染为高亮块
          pre: ({ children }) => {
            const child = Array.isArray(children) ? children[0] : children
            if (!isValidElement<{ className?: unknown; children?: unknown }>(child)) {
              return <pre>{children}</pre>
            }
            const childProps = (child as ReactElement<{ className?: string; children?: unknown }>).props ?? {}
            const match = /language-([\w-]+)/.exec(
              typeof childProps.className === 'string' ? childProps.className : '',
            )
            return (
              <CodeBlock
                code={String(childProps.children ?? '').replace(/\n$/, '')}
                language={match?.[1]}
              />
            )
          },
          // 行内 code：保持默认样式
          code: ({ className, children }) => <code className={className}>{children}</code>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
