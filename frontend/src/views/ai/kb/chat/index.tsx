import {
  Alert,
  App,
  Button,
  Collapse,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Select,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useRef, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import {
  kbApi,
  streamKBChat,
  type Citation,
  type ConversationItem,
  type KBBase,
  type SearchHit,
} from '@/api/kb'

/** 页面内消息模型：历史加载与流式生成共用 */
interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  /** 本轮多轮改写后的检索词（meta 事件下发） */
  searchQuery?: string
  citations?: Citation[]
  streaming?: boolean
  stopped?: boolean
}

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

export default function KBChat() {
  const { message } = App.useApp()
  const [searchForm] = Form.useForm<{ query: string; top_k: number }>()

  // ---------- 知识库选择 ----------
  const [kbOptions, setKbOptions] = useState<KBBase[]>([])
  const [kbIds, setKbIds] = useState<number[]>([])

  // ---------- 会话列表 ----------
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [convTotal, setConvTotal] = useState(0)
  const [convPage, setConvPage] = useState(1)
  const [currentConvId, setCurrentConvId] = useState<number | null>(null)

  // ---------- 消息与流式状态 ----------
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // ---------- 检索调试 ----------
  const [searchOpen, setSearchOpen] = useState(false)
  const [searching, setSearching] = useState(false)
  const [hits, setHits] = useState<SearchHit[]>([])

  const loadConversations = useCallback(async (page: number) => {
    try {
      const res = await kbApi.conversations({ page, page_size: 50 })
      setConversations((prev) => (page === 1 ? res.list : [...prev, ...res.list]))
      setConvTotal(res.total)
      setConvPage(page)
    } catch {
      // 错误已由拦截器统一提示
    }
  }, [])

  useEffect(() => {
    loadConversations(1)
  }, [loadConversations])

  const loadKbs = useCallback(async () => {
    try {
      const res = await kbApi.list({ page: 1, page_size: 100 })
      setKbOptions(res.list)
      // 默认选中第一个库，降低上手成本
      if (res.list.length > 0) setKbIds((prev) => (prev.length ? prev : [res.list[0].id]))
    } catch {
      // 错误已由拦截器统一提示
    }
  }, [])

  useEffect(() => {
    loadKbs()
  }, [loadKbs])

  // 消息变化（含流式增量）后滚动到底部
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const openConversation = async (conv: ConversationItem) => {
    if (streaming) {
      message.warning('正在生成回答，请先停止')
      return
    }
    try {
      const detail = await kbApi.conversation(conv.id)
      setCurrentConvId(conv.id)
      setMessages(
        detail.messages
          .filter((m) => m.role !== 'tool')
          .map((m) => ({
            role: m.role === 'user' ? ('user' as const) : ('assistant' as const),
            content: m.content,
            citations: m.citations || [],
          })),
      )
    } catch {
      // 错误已由拦截器统一提示
    }
  }

  const newConversation = () => {
    if (streaming) {
      message.warning('正在生成回答，请先停止')
      return
    }
    setCurrentConvId(null)
    setMessages([])
  }

  const patchAssistant = (patch: Partial<ChatMsg>) =>
    setMessages((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last && last.role === 'assistant') next[next.length - 1] = { ...last, ...patch }
      return next
    })

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    if (!kbIds.length) {
      message.warning('请先选择至少一个知识库')
      return
    }

    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '', citations: [], streaming: true }])
    setInput('')
    setStreaming(true)

    let answer = ''
    let reasoning = ''
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamKBChat(
        { question: text, kb_ids: kbIds, conversation_id: currentConvId, top_k: 6 },
        {
          onMeta: (d) => {
            patchAssistant({ searchQuery: d.search_query })
            if (d.conversation_id !== currentConvId) {
              setCurrentConvId(d.conversation_id)
              // 新会话：乐观插入列表头部（完成后仍会刷新一次）
              const now = new Date().toISOString()
              setConversations((prev) => [
                { id: d.conversation_id, title: text.slice(0, 32), created_at: now, updated_at: now },
                ...prev,
              ])
              setConvTotal((n) => n + 1)
            }
          },
          onMessage: (delta) => {
            answer += delta
            patchAssistant({ content: answer })
          },
          onReasoning: (delta) => {
            reasoning += delta
            patchAssistant({ reasoning })
          },
          onCitations: (citations) => patchAssistant({ citations }),
          onDone: () => patchAssistant({ streaming: false }),
          onError: (msg) => {
            patchAssistant({ streaming: false })
            if (!answer) patchAssistant({ content: `（生成失败：${msg}）` })
            message.error(msg)
          },
        },
        controller.signal,
      )
    } catch (err) {
      const e = err as Error
      patchAssistant({ streaming: false })
      if (e.name === 'AbortError') {
        patchAssistant({ stopped: true })
      } else {
        if (!answer) patchAssistant({ content: '（生成中断）' })
        message.error(e.name === 'TypeError' ? '网络异常，请稍后重试' : e.message || '网络异常，请稍后重试')
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
      loadConversations(1)
    }
  }

  const stop = () => {
    abortRef.current?.abort()
  }

  const handleSearchDebug = async (values: { query: string; top_k: number }) => {
    if (!kbIds.length) {
      message.warning('请先在顶部选择知识库')
      return
    }
    setSearching(true)
    try {
      const res = await kbApi.search({ query: values.query.trim(), kb_ids: kbIds, top_k: values.top_k })
      setHits(res)
    } finally {
      setSearching(false)
    }
  }

  const renderCitations = (citations: Citation[]) => (
    <div style={{ marginTop: 8, borderTop: '1px dashed #e8e8e8', paddingTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      <Typography.Text type="secondary" style={{ fontSize: 12, width: '100%' }}>引用来源</Typography.Text>
      {citations.map((c) => (
        <Tooltip
          key={c.index}
          title={
            <div style={{ maxWidth: 360 }}>
              <div>{c.snippet}</div>
              {c.similarity != null && <div style={{ marginTop: 4 }}>相似度：{c.similarity}</div>}
            </div>
          }
        >
          <Tag style={{ cursor: 'default', fontSize: 12 }}>
            [{c.index}] {c.file_name || '未知文件'}
            {c.title_path ? ` · ${c.title_path}` : ''}
            {c.page ? ` · 第${c.page}页` : ''}
          </Tag>
        </Tooltip>
      ))}
    </div>
  )

  const renderMessage = (m: ChatMsg, idx: number) => {
    if (m.role === 'user') {
      return (
        <div key={idx} style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
          <div
            style={{
              background: '#e6f4ff',
              padding: '10px 14px',
              borderRadius: 8,
              maxWidth: '75%',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              lineHeight: 1.7,
            }}
          >
            {m.content}
          </div>
        </div>
      )
    }
    return (
      <div key={idx} style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
        <div
          style={{
            background: '#f5f5f5',
            padding: '10px 14px',
            borderRadius: 8,
            maxWidth: '85%',
            minWidth: 120,
          }}
        >
          {m.searchQuery && (
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>
              检索词：{m.searchQuery}
            </Typography.Paragraph>
          )}
          {m.reasoning && (
            <Collapse
              ghost
              size="small"
              style={{ marginBottom: 4, marginLeft: -12 }}
              items={[
                {
                  key: 'reasoning',
                  label: <Typography.Text type="secondary" style={{ fontSize: 12 }}>思考过程</Typography.Text>,
                  children: (
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#888', maxHeight: 240, overflowY: 'auto' }}>
                      {m.reasoning}
                    </div>
                  ),
                },
              ]}
            />
          )}
          {(m.content || m.streaming) && (
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.7 }}>
              {m.content}
              {m.streaming ? '▍' : ''}
            </div>
          )}
          {m.stopped && <Typography.Text type="secondary" style={{ fontSize: 12 }}>已停止生成</Typography.Text>}
          {m.citations && m.citations.length > 0 && renderCitations(m.citations)}
        </div>
      </div>
    )
  }

  const hitColumns = [
    { title: '来源库', dataIndex: 'kb_name', width: 100, ellipsis: true },
    { title: '文件名', dataIndex: 'file_name', width: 140, ellipsis: true },
    {
      title: '标题路径',
      dataIndex: 'title_path',
      width: 160,
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    { title: '页码', dataIndex: 'page', width: 65, render: (v: number | null) => (v == null ? '-' : v) },
    { title: '相似度', dataIndex: 'similarity', width: 80, render: (v: number) => v.toFixed(4) },
    {
      title: '切片内容',
      dataIndex: 'content',
      render: (v: string) => (
        <Typography.Paragraph ellipsis={{ rows: 3, expandable: true, symbol: '展开' }} style={{ marginBottom: 0 }}>
          {v}
        </Typography.Paragraph>
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', gap: 12, height: 'calc(100vh - 96px)' }}>
      {/* 左侧：会话列表 */}
      <div
        style={{
          width: 260,
          flexShrink: 0,
          background: '#fff',
          borderRadius: 8,
          border: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            padding: '10px 12px',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Typography.Text strong>会话列表</Typography.Text>
          <Button size="small" icon={<PlusOutlined />} onClick={newConversation}>新建</Button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
          {conversations.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无会话" />
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => openConversation(c)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  marginBottom: 4,
                  background: currentConvId === c.id ? '#e6f4ff' : undefined,
                }}
              >
                <Typography.Text ellipsis={{ tooltip: c.title }} style={{ maxWidth: 210, display: 'block' }}>
                  {c.title}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>{fmtTime(c.updated_at)}</Typography.Text>
              </div>
            ))
          )}
          {conversations.length < convTotal && (
            <Button type="link" size="small" block onClick={() => loadConversations(convPage + 1)}>
              加载更多
            </Button>
          )}
        </div>
      </div>

      {/* 右侧：选库 + 消息流 + 输入区 */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          background: '#fff',
          borderRadius: 8,
          border: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '10px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', gap: 8 }}>
          <Select
            mode="multiple"
            allowClear
            placeholder="选择知识库（可多选）"
            style={{ flex: 1, minWidth: 0 }}
            value={kbIds}
            onChange={setKbIds}
            options={kbOptions.map((k) => ({ value: k.id, label: k.name }))}
            maxTagCount="responsive"
          />
          <HasPermission code="kb:search">
            <Button icon={<SearchOutlined />} onClick={() => setSearchOpen(true)}>
              检索调试
            </Button>
          </HasPermission>
        </div>

        <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          {messages.length === 0 ? (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Typography.Title level={4} style={{ marginBottom: 8 }}>知识库问答调试</Typography.Title>
              <Typography.Text type="secondary">
                选择知识库后输入问题，回答基于文档内容生成并附引用来源（文件名 · 标题路径 · 页码）。
              </Typography.Text>
            </div>
          ) : (
            messages.map(renderMessage)
          )}
        </div>

        <div style={{ borderTop: '1px solid #f0f0f0', padding: 12 }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            autoSize={{ minRows: 2, maxRows: 5 }}
            disabled={streaming}
            onKeyDown={(e) => {
              // 中文输入法组合期间的 Enter 不触发发送
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                send()
              }
            }}
          />
          <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 8 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {currentConvId ? `当前会话 #${currentConvId}` : '新会话'}
            </Typography.Text>
            {streaming ? (
              <Button danger onClick={stop}>停止</Button>
            ) : (
              <Button type="primary" onClick={send} disabled={!input.trim()}>发送</Button>
            )}
          </div>
        </div>
      </div>

      {/* 检索调试抽屉 */}
      <Drawer title="检索调试" open={searchOpen} onClose={() => setSearchOpen(false)} width={780}>
        <Form
          layout="inline"
          form={searchForm}
          initialValues={{ top_k: 6 }}
          onFinish={handleSearchDebug}
          style={{ marginBottom: 16, rowGap: 12 }}
        >
          <Form.Item name="query" rules={[{ required: true, message: '请输入查询内容' }]} style={{ minWidth: 320 }}>
            <Input placeholder="输入查询内容" allowClear />
          </Form.Item>
          <Form.Item name="top_k" label="Top K">
            <InputNumber min={1} max={20} precision={0} style={{ width: 70 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={searching}>检索</Button>
          </Form.Item>
        </Form>
        {kbIds.length === 0 && (
          <Alert type="warning" showIcon message="请先在顶部选择知识库" style={{ marginBottom: 12 }} />
        )}
        <Table
          rowKey={(r) => `${r.kb_id}-${r.file_id}-${r.chunk_index ?? 'x'}`}
          size="small"
          columns={hitColumns}
          dataSource={hits}
          loading={searching}
          pagination={false}
          locale={{ emptyText: '暂无结果，检索后展示命中切片' }}
        />
      </Drawer>
    </div>
  )
}
