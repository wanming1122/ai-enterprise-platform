import {
  App,
  Button,
  Collapse,
  Input,
  Popconfirm,
  Space,
  Switch,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  DatabaseOutlined,
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  aiChatApi,
  streamAIChat,
  type AIConversationItem,
  type AIToolEvent,
} from '@/api/aiChat'
import type { Citation } from '@/api/kb'
import MarkdownText from '@/components/MarkdownText'
import ThinkingIndicator from '@/components/ThinkingIndicator'
import { useUserStore } from '@/stores/user'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '')

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  tools?: AIToolEvent[]
  citations?: Citation[]
  streaming?: boolean
  stopped?: boolean
}

export default function AIChat() {
  const { message } = App.useApp()
  const userInfo = useUserStore((s) => s.userInfo)

  const [conversations, setConversations] = useState<AIConversationItem[]>([])
  const [convTotal, setConvTotal] = useState(0)
  const [convPage, setConvPage] = useState(1)
  const [currentConvId, setCurrentConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [deepThinking, setDeepThinking] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)

  const loadConversations = useCallback(async (p: number) => {
    const res = await aiChatApi.conversations({ page: p, page_size: 20 })
    setConversations((prev) => (p === 1 ? res.list : [...prev, ...res.list]))
    setConvTotal(res.total)
    setConvPage(p)
  }, [])

  useEffect(() => {
    loadConversations(1)
  }, [loadConversations])

  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const newConversation = () => {
    if (streaming) {
      message.warning('请先停止当前生成')
      return
    }
    setCurrentConvId(null)
    setMessages([])
  }

  const openConversation = async (id: number) => {
    if (streaming) {
      message.warning('请先停止当前生成')
      return
    }
    const detail = await aiChatApi.conversation(id)
    setCurrentConvId(id)
    // tool 消息附着到 assistant 消息上以标签展示（兼容 tool 在前/在后两种落库顺序）
    const list: ChatMsg[] = []
    let pendingTools: AIToolEvent[] = []
    for (const m of detail.messages) {
      if (m.role === 'user') {
        list.push({ role: 'user', content: m.content })
      } else if (m.role === 'tool') {
        pendingTools.push({ tool: m.tool_name ?? '' })
      } else {
        list.push({
          role: 'assistant',
          content: m.content,
          reasoning: m.reasoning_content ?? undefined,
          tools: pendingTools.length ? pendingTools : undefined,
          citations: m.citations ?? undefined,
        })
        pendingTools = []
      }
    }
    if (pendingTools.length) {
      for (let i = list.length - 1; i >= 0; i--) {
        if (list[i].role === 'assistant') {
          list[i].tools = [...(list[i].tools ?? []), ...pendingTools]
          break
        }
      }
    }
    setMessages(list)
  }

  const removeConversation = async (id: number) => {
    await aiChatApi.removeConversation(id)
    message.success('会话已删除')
    if (currentConvId === id) newConversation()
    loadConversations(1)
  }

  const patchAssistant = (patch: Partial<ChatMsg>) => {
    setMessages((prev) => {
      if (!prev.length) return prev
      const last = prev[prev.length - 1]
      return [...prev.slice(0, -1), { ...last, ...patch }]
    })
  }

  const send = async () => {
    const question = input.trim()
    if (!question || streaming) return
    setInput('')
    setStreaming(true)
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '', tools: [], citations: [], streaming: true },
    ])

    const controller = new AbortController()
    abortRef.current = controller
    let answer = ''
    let reasoning = ''
    let tools: AIToolEvent[] = []

    try {
      await streamAIChat(
        { question, conversation_id: currentConvId, deep_thinking: deepThinking },
        {
          onMeta: ({ conversation_id }) => {
            if (currentConvId == null) {
              setCurrentConvId(conversation_id)
              setConversations((prev) => [
                { id: conversation_id, title: question.slice(0, 32), created_at: '', updated_at: '' },
                ...prev,
              ])
            }
          },
          onTool: (ev) => {
            tools = [...tools, ev]
            patchAssistant({ tools })
          },
          onReasoning: (delta) => {
            reasoning += delta
            patchAssistant({ reasoning })
          },
          onMessage: (delta) => {
            answer += delta
            patchAssistant({ content: answer })
          },
          onCitations: (list) => {
            patchAssistant({ citations: list })
          },
          onDone: () => {
            patchAssistant({ streaming: false })
            loadConversations(1)
          },
          onError: (msg) => {
            patchAssistant({ streaming: false, stopped: true })
            message.error(msg)
          },
        },
        controller.signal,
      )
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') {
        patchAssistant({ streaming: false, stopped: true })
      } else {
        patchAssistant({ streaming: false, stopped: true })
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const stop = () => {
    abortRef.current?.abort()
  }

  const renderToolChips = (tools?: AIToolEvent[]) => {
    if (!tools?.length) return null
    return (
      <Space size={4} wrap style={{ marginBottom: 6 }}>
        {tools.map((t, i) => {
          if (t.tool === 'retrieve') {
            return (
              <Tag key={i} icon={<SearchOutlined />} color="processing" style={{ marginInlineEnd: 0 }}>
                已检索知识库{t.query ? `：${t.query}` : ''}
              </Tag>
            )
          }
          if (t.tool === 'nl2sql') {
            return (
              <Tag key={i} icon={<DatabaseOutlined />} color="success" style={{ marginInlineEnd: 0 }}>
                已查询产品数据{t.question ? `：${t.question}` : ''}
              </Tag>
            )
          }
          return <Tag key={i}>{t.tool}</Tag>
        })}
      </Space>
    )
  }

  const renderCitations = (citations?: Citation[]) => {
    if (!citations?.length) return null
    return (
      <div style={{ borderTop: '1px dashed #d9d9d9', marginTop: 8, paddingTop: 6 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          引用来源
        </Typography.Text>
        <Space size={4} wrap>
          {citations.map((c) => (
            <Tooltip
              key={c.index}
              title={
                <div style={{ maxWidth: 360 }}>
                  <div>{c.snippet}</div>
                  {c.similarity != null && <div>相似度：{c.similarity}</div>}
                </div>
              }
            >
              <Tag style={{ marginInlineEnd: 0 }}>
                [{c.index}] {c.file_name || '未知文件'}
                {c.title_path ? ` · ${c.title_path}` : ''}
                {c.page ? ` · 第${c.page}页` : ''}
              </Tag>
            </Tooltip>
          ))}
        </Space>
      </div>
    )
  }

  const renderMessage = (m: ChatMsg, idx: number) => {
    if (m.role === 'user') {
      return (
        <div key={idx} style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
          <div
            style={{
              background: '#e6f4ff',
              padding: '8px 12px',
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
      <div key={idx} style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
        <div
          style={{
            background: '#f5f5f5',
            padding: '8px 12px',
            borderRadius: 8,
            maxWidth: '85%',
            minWidth: 120,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            lineHeight: 1.7,
          }}
        >
          {renderToolChips(m.tools)}
          {m.reasoning && (
            <Collapse
              ghost
              size="small"
              style={{ margin: '0 0 6px' }}
              items={[
                {
                  key: 'reasoning',
                  label: <span style={{ fontSize: 12 }}>思考过程</span>,
                  children: (
                    <div
                      style={{
                        fontSize: 12,
                        color: '#8c8c8c',
                        whiteSpace: 'pre-wrap',
                        maxHeight: 240,
                        overflowY: 'auto',
                      }}
                    >
                      {m.reasoning}
                    </div>
                  ),
                },
              ]}
            />
          )}
          {m.content ? (
            // 流式中把光标字符拼进正文末尾，保证跟随最后一个段落行内显示
            <MarkdownText content={m.streaming ? `${m.content}▍` : m.content} />
          ) : m.streaming ? (
            <ThinkingIndicator />
          ) : null}
          {m.stopped && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              已停止生成
            </Typography.Text>
          )}
          {renderCitations(m.citations)}
        </div>
      </div>
    )
  }

  const currentTitle = conversations.find((c) => c.id === currentConvId)?.title

  return (
    <div style={{ display: 'flex', gap: 12, height: 'calc(100vh - 96px)' }}>
      {/* 左侧：会话列表 */}
      <div
        style={{
          width: 260,
          background: '#fff',
          borderRadius: 8,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Button type="primary" icon={<PlusOutlined />} block onClick={newConversation}>
          新建会话
        </Button>
        <div style={{ flex: 1, overflowY: 'auto', marginTop: 12 }}>
          {conversations.map((c) => (
            <div
              key={c.id}
              onClick={() => openConversation(c.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 6,
                padding: '8px 10px',
                borderRadius: 6,
                marginBottom: 4,
                cursor: 'pointer',
                background: c.id === currentConvId ? '#e6f4ff' : undefined,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 13,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {c.title || '未命名会话'}
                </div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {fmtTime(c.updated_at)}
                </Typography.Text>
              </div>
              <Popconfirm
                title="确认删除该会话？"
                description="删除后不再显示。"
                onConfirm={(e) => {
                  e?.stopPropagation()
                  removeConversation(c.id)
                }}
                onCancel={(e) => e?.stopPropagation()}
              >
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()}
                />
              </Popconfirm>
            </div>
          ))}
          {conversations.length < convTotal && (
            <Button type="link" size="small" block onClick={() => loadConversations(convPage + 1)}>
              加载更多
            </Button>
          )}
        </div>
      </div>

      {/* 右侧：对话区 */}
      <div
        style={{
          flex: 1,
          background: '#fff',
          borderRadius: 8,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f0f0f0',
            paddingBottom: 8,
            marginBottom: 8,
          }}
        >
          <Space size={12}>
            <Typography.Text strong>
              {currentConvId ? currentTitle || `会话 #${currentConvId}` : '新会话'}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              企业管理场景对话入口
            </Typography.Text>
          </Space>
          <Space size={12}>
            <Space size={6}>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>深度思考</Typography.Text>
              <Switch
                size="small"
                checked={deepThinking}
                checkedChildren="开"
                unCheckedChildren="关"
                onChange={setDeepThinking}
                disabled={streaming}
              />
            </Space>
            <Button icon={<ReloadOutlined />} size="small" onClick={() => loadConversations(1)}>
              刷新
            </Button>
          </Space>
        </div>

        <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '4px 4px' }}>
          {messages.length === 0 ? (
            <div
              style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              <Typography.Title level={4} style={{ margin: 0 }}>
                你好，{userInfo?.nickname || userInfo?.username || '朋友'}
              </Typography.Title>
              <Typography.Text type="secondary">
                可询问公司制度、流程等知识库问题，也可以查询产品库存、价格等数据
              </Typography.Text>
            </div>
          ) : (
            messages.map(renderMessage)
          )}
        </div>

        <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="可以询问制度、流程等知识库问题；涉及产品数据会自动查询 product 表"
            autoSize={{ minRows: 2, maxRows: 5 }}
            maxLength={2000}
            disabled={streaming}
            onPressEnter={(e) => {
              if (!e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                send()
              }
            }}
          />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: 8,
            }}
          >
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {currentConvId ? `会话 #${currentConvId}` : '回车发送，Shift+回车换行'}
            </Typography.Text>
            {streaming ? (
              <Button danger icon={<StopOutlined />} onClick={stop}>
                停止
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<SendOutlined />}
                disabled={!input.trim()}
                onClick={send}
              >
                发送
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
