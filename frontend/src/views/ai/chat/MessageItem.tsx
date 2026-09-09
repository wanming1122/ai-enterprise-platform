/**
 * 单条消息渲染（AI 助手页）。
 * - 用户右侧气泡：图片附件；hover 操作栏「复制 / 编辑」（编辑态替换为 TextArea，确认后重发）
 * - 助手左侧气泡：工具标签、思考过程折叠面板（流式展开→结束自动收起并显示思考时长，可手动开合）、
 *   MarkdownText、引用来源（点击打开详情 Drawer，可跳知识库文件页）、流式光标
 * - 错误态：气泡红框 + 内嵌错误信息 + 重试按钮（区分「用户停止」与「服务端错误」）
 */
import { memo, useEffect, useState, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Collapse,
  Drawer,
  Image as AntImage,
  Input,
  Progress,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  BulbOutlined,
  CheckOutlined,
  CloudServerOutlined,
  CopyOutlined,
  DatabaseOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  WifiOutlined,
} from '@ant-design/icons'
import type { AIToolEvent } from '@/api/aiChat'
import type { Citation } from '@/api/kb'
import MarkdownText from '@/components/MarkdownText'
import ThinkingIndicator from '@/components/ThinkingIndicator'
import type { ChatMsg } from './useChat'

/** 相似度取值可能是 [0,1] 或百分数，统一钳制到进度条 0-100 */
function toPercent(sim: number | null | undefined): number {
  if (sim == null) return 0
  const raw = sim <= 1 ? sim * 100 : sim
  return Math.min(100, Math.max(0, raw))
}

/** 工具调用标签：按工具类型着色 */
function renderToolChips(tools?: AIToolEvent[]) {
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
        if (t.tool === 'server_admin') {
          return (
            <Tag key={i} icon={<CloudServerOutlined />} color="warning" style={{ marginInlineEnd: 0 }}>
              已查询服务器{t.action ? `：${t.action}${t.path ? ` · ${t.path}` : ''}` : ''}
            </Tag>
          )
        }
        if (t.tool === 'nl2sql') {
          return (
            <Tag key={i} icon={<DatabaseOutlined />} color="success" style={{ marginInlineEnd: 0 }}>
              已查询业务数据{t.question ? `：${t.question}` : ''}
            </Tag>
          )
        }
        return <Tag key={i}>{t.tool}</Tag>
      })}
    </Space>
  )
}

interface Props {
  msg: ChatMsg
  /** 消息在列表中的索引：编辑提交时定位被修改的提问 */
  messageIndex?: number
  /** 展示「重新生成」入口（对话末尾且非流式中） */
  showRegenerate?: boolean
  /** 展示「编辑」入口（用户提问且非流式中） */
  showEdit?: boolean
  /** 错误消息的「重试」按钮（错误且为最后一条助手消息） */
  showRetry?: boolean
  /** SSE 已建立连接（meta 事件已到），区分「连接中/思考中」 */
  connected?: boolean
  /** 流式超 15s 无增量（提示可等待或停止） */
  slow?: boolean
  onRegenerate?: () => void
  onRetry?: () => void
  onEditMessage?: (index: number, text: string) => void
}

function MessageItemInner({
  msg,
  messageIndex = -1,
  showRegenerate,
  showEdit,
  showRetry,
  connected,
  slow,
  onRegenerate,
  onRetry,
  onEditMessage,
}: Props) {
  const [copied, setCopied] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  // 思考面板开合：默认「流式中展开、结束收起」；用户手动开/合后以其选择为准
  const [userReasoningOpen, setUserReasoningOpen] = useState<boolean | null>(null)
  const reasoningOpen = userReasoningOpen ?? !!msg.streaming
  const [citationDetail, setCitationDetail] = useState<Citation | null>(null)
  const navigate = useNavigate()

  // 本条消息不再含思考内容（新问答/换会话）时，清空手动开合选择回到默认策略
  useEffect(() => {
    if (!msg.reasoning) setUserReasoningOpen(null)
  }, [msg.reasoning])

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // 剪贴板不可用时静默忽略
    }
  }

  const startEdit = () => {
    setDraft(msg.content)
    setEditing(true)
  }

  const submitEdit = () => {
    if (onEditMessage) onEditMessage(messageIndex, draft)
    setEditing(false)
  }

  const bubbleStyle: CSSProperties = msg.error
    ? {
        background: 'var(--ant-color-error-bg)',
        border: '1px solid var(--ant-color-error-border)',
      }
    : {
        background: 'var(--ant-color-fill-tertiary)',
      }

  const reasoningLabel =
    !msg.streaming && msg.reasoningSeconds != null
      ? `思考过程 · ${msg.reasoningSeconds}s`
      : '思考过程'

  if (msg.role === 'user') {
    return (
      <div className="chat-msg-row" style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        {editing ? (
          <div
            style={{
              maxWidth: '75%',
              background: 'var(--ant-color-primary-bg)',
              padding: 8,
              borderRadius: 8,
            }}
          >
            <Input.TextArea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoSize={{ minRows: 2, maxRows: 8 }}
              maxLength={2000}
            />
            <Space style={{ marginTop: 6 }}>
              <Button size="small" type="primary" disabled={!draft.trim()} onClick={submitEdit}>
                发送
              </Button>
              <Button size="small" onClick={() => setEditing(false)}>
                取消
              </Button>
            </Space>
          </div>
        ) : (
          <>
            <div
              style={{
                background: 'var(--ant-color-primary-bg)',
                padding: '8px 12px',
                borderRadius: 8,
                maxWidth: '75%',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                lineHeight: 1.7,
              }}
            >
              {msg.attachments && msg.attachments.length > 0 && (
                <AntImage.PreviewGroup>
                  <Space size={6} wrap style={{ marginBottom: msg.content ? 6 : 0 }}>
                    {msg.attachments.map((a, i) => (
                      <AntImage
                        key={i}
                        src={a.url}
                        width={110}
                        style={{ borderRadius: 6, objectFit: 'cover' }}
                      />
                    ))}
                  </Space>
                </AntImage.PreviewGroup>
              )}
              {msg.content}
            </div>
            <span className="chat-actions">
              <Button
                type="text"
                size="small"
                title="复制"
                icon={copied ? <CheckOutlined style={{ color: 'var(--ant-color-success)' }} /> : <CopyOutlined />}
                onClick={() => copy(msg.content)}
              />
              {showEdit && (
                <Button type="text" size="small" title="编辑并重新提问" icon={<EditOutlined />} onClick={startEdit} />
              )}
            </span>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="chat-msg-row" style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
      <div
        style={{
          ...bubbleStyle,
          padding: '8px 12px',
          borderRadius: 8,
          maxWidth: '85%',
          minWidth: 120,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          lineHeight: 1.7,
        }}
      >
        {renderToolChips(msg.tools)}
        {!!msg.memoryCount && (
          <div style={{ marginBottom: 6 }}>
            <Tooltip title="本轮从你的长期记忆中召回了相关内容注入回答上下文">
              <Tag icon={<BulbOutlined />} color="purple">
                参考了 {msg.memoryCount} 条长期记忆
              </Tag>
            </Tooltip>
          </div>
        )}
        {msg.reasoning && (
          <Collapse
            ghost
            size="small"
            style={{ margin: '0 0 6px' }}
            activeKey={reasoningOpen ? ['reasoning'] : []}
            destroyInactivePanel
            onChange={(keys) => setUserReasoningOpen(keys.includes('reasoning'))}
            items={[
              {
                key: 'reasoning',
                label: <span style={{ fontSize: 12 }}>{reasoningLabel}</span>,
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
                    {msg.reasoning}
                  </div>
                ),
              },
            ]}
          />
        )}
        {msg.content ? (
          <div>
            <MarkdownText content={msg.content} />
            {/* 流式光标：独立 CSS 动画元素，不拼入 Markdown 文本 */}
            {msg.streaming && <span className="chat-caret" aria-hidden />}
          </div>
        ) : msg.streaming ? (
          <ThinkingIndicator text={connected ? undefined : '连接模型中…'} />
        ) : null}
        {msg.streaming && slow && (
          <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
            模型响应较慢，可继续等待或按 Enter 停止
          </Typography.Text>
        )}
        {msg.error && msg.errorText && (
          <div style={{ marginTop: 6 }}>
            <Space size={4} align="start">
              {msg.errorType === 'network' ? (
                <WifiOutlined style={{ color: 'var(--ant-color-error)', marginTop: 2 }} />
              ) : (
                <ExclamationCircleOutlined style={{ color: 'var(--ant-color-error)', marginTop: 2 }} />
              )}
              <div>
                <Typography.Text type="danger" style={{ fontSize: 12, display: 'block' }}>
                  {msg.errorText}
                </Typography.Text>
                {msg.errorAction && (
                  <Typography.Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                    {msg.errorAction}
                  </Typography.Text>
                )}
              </div>
            </Space>
          </div>
        )}
        {msg.stopped && !msg.error && (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            已停止生成
          </Typography.Text>
        )}
        {msg.stats && !msg.streaming && (
          <Typography.Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
            耗时 {(msg.stats.duration_ms / 1000).toFixed(1)}s · 输入 {msg.stats.prompt_tokens.toLocaleString()} /
            输出 {msg.stats.completion_tokens.toLocaleString()} tokens
            {msg.stats.estimated ? '（估算）' : ''}
          </Typography.Text>
        )}
        {msg.error && showRetry && (
          <Space style={{ marginTop: 6 }}>
            <Button size="small" type="primary" danger icon={<ReloadOutlined />} onClick={onRetry}>
              重试
            </Button>
          </Space>
        )}
        {msg.citations && msg.citations.length > 0 && (
          <div style={{ borderTop: '1px dashed var(--ant-color-border)', marginTop: 8, paddingTop: 6 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              引用来源
            </Typography.Text>
            <Space size={4} wrap>
              {msg.citations.map((c) => (
                <Tooltip
                  key={c.index}
                  title={
                    <div style={{ maxWidth: 360 }}>
                      <div>{c.snippet}</div>
                      {c.similarity != null && <div>相似度：{c.similarity}</div>}
                    </div>
                  }
                >
                  <Tag
                    style={{ marginInlineEnd: 0, cursor: 'pointer' }}
                    onClick={() => setCitationDetail(c)}
                  >
                    [{c.index}] {c.file_name || '未知文件'}
                    {c.title_path ? ` · ${c.title_path}` : ''}
                    {c.page ? ` · 第${c.page}页` : ''}
                  </Tag>
                </Tooltip>
              ))}
            </Space>
          </div>
        )}
      </div>
      <span className="chat-actions">
        <Button
          type="text"
          size="small"
          title="复制 Markdown"
          icon={copied ? <CheckOutlined style={{ color: 'var(--ant-color-success)' }} /> : <CopyOutlined />}
          onClick={() => copy(msg.content)}
        />
        {showRegenerate && !msg.error && (
          <Button type="text" size="small" title="重新生成" icon={<ReloadOutlined />} onClick={onRegenerate} />
        )}
      </span>

      {/* 引用来源详情 */}
      <Drawer
        open={citationDetail != null}
        title={citationDetail?.file_name || '引用来源'}
        width={480}
        onClose={() => setCitationDetail(null)}
        footer={
          <Button
            type="primary"
            block
            onClick={() => {
              setCitationDetail(null)
              navigate('/ai/kb')
            }}
          >
            查看完整文件
          </Button>
        }
      >
        {citationDetail && (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Typography.Text strong>{citationDetail.snippet}</Typography.Text>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                文档位置
              </Typography.Text>
              <div>
                {[citationDetail.file_name, citationDetail.title_path, citationDetail.page ? `第${citationDetail.page}页` : '']
                  .filter(Boolean)
                  .join(' · ') || '—'}
              </div>
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                相关度
              </Typography.Text>
              <Progress
                percent={toPercent(citationDetail.similarity)}
                size="small"
                format={(p) => (citationDetail.similarity != null ? String(citationDetail.similarity) : `${p}%`)}
              />
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                片段内容
              </Typography.Text>
              <div
                style={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontSize: 13,
                  background: 'var(--ant-color-fill-quaternary)',
                  padding: 8,
                  borderRadius: 6,
                  marginTop: 4,
                }}
              >
                {citationDetail.snippet}
              </div>
            </div>
          </Space>
        )}
      </Drawer>
    </div>
  )
}

/** memo 化：流式增量只更新最后一条消息，其余消息（props 引用未变）跳过重渲 */
const MessageItem = memo(MessageItemInner)
export default MessageItem
