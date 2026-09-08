/**
 * 会话侧边栏（AI 助手页，M7）：搜索（防抖+标题高亮）、时间分组（今天/昨天/近7天/更早）、
 * 置顶分组与置顶按钮、双击重命名、分页加载/切换/删除。
 * 数据与写操作由页面容器/useChat 提供；置顶与重命名采用乐观更新。
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Button, Input, Popconfirm, Typography } from 'antd'
import {
  DeleteOutlined,
  PlusOutlined,
  PushpinOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import type { AIConversationItem } from '@/api/aiChat'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '')

/** 时间分组标签 */
function groupLabel(ts: string): string {
  const day = dayjs(ts)
  if (!day.isValid()) return '今天'
  const diff = dayjs().startOf('day').diff(day.startOf('day'), 'day')
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff <= 7) return '近 7 天'
  return '更早'
}

const GROUP_ORDER = ['今天', '昨天', '近 7 天', '更早']

interface Props {
  conversations: AIConversationItem[]
  convTotal: number
  currentConvId: number | null
  onNew: () => void
  onOpen: (id: number) => void
  onRemove: (id: number) => void
  onLoadMore: () => void
  onRename: (id: number, title: string) => void
  onTogglePin: (id: number) => void
}

export default function ConversationSidebar({
  conversations,
  convTotal,
  currentConvId,
  onNew,
  onOpen,
  onRemove,
  onLoadMore,
  onRename,
  onTogglePin,
}: Props) {
  const [searchInput, setSearchInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 搜索防抖 300ms（本地内存过滤）
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setKeyword(searchInput.trim()), 300)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [searchInput])

  const visible = useMemo(() => {
    const kw = keyword.toLowerCase()
    const hit = (c: AIConversationItem) =>
      !kw || (c.title || '未命名会话').toLowerCase().includes(kw)
    const filtered = conversations.filter(hit)
    const pinned = filtered.filter((c) => c.pinned)
    const rest = filtered.filter((c) => !c.pinned)
    const buckets = new Map<string, AIConversationItem[]>()
    for (const c of rest) {
      const key = c.updated_at ? groupLabel(c.updated_at) : '今天'
      const arr = buckets.get(key)
      if (arr) arr.push(c)
      else buckets.set(key, [c])
    }
    return { pinned, buckets }
  }, [conversations, keyword])

  /** 标题命中关键词高亮 */
  const highlight = (title: string): ReactNode => {
    const k = keyword
    if (!k) return title
    const idx = title.toLowerCase().indexOf(k.toLowerCase())
    if (idx < 0) return title
    return (
      <>
        {title.slice(0, idx)}
        <Typography.Text mark>{title.slice(idx, idx + k.length)}</Typography.Text>
        {title.slice(idx + k.length)}
      </>
    )
  }

  const startEdit = (c: AIConversationItem) => {
    setDraft(c.title ?? '')
    setEditingId(c.id)
  }

  const commitEdit = (id: number) => {
    setEditingId(null)
    if (draft.trim() && draft.trim() !== conversations.find((c) => c.id === id)?.title) {
      onRename(id, draft)
    }
  }

  const renderItem = (c: AIConversationItem) => {
    const isEditing = editingId === c.id
    const displayTitle = c.title || '未命名会话'
    const isCurrent = c.id === currentConvId
    return (
      <div
        key={c.id}
        className="chat-msg-row"
        onClick={() => {
          if (!isEditing) onOpen(c.id)
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
          padding: '8px 10px',
          borderRadius: 6,
          marginBottom: 4,
          cursor: 'pointer',
          background: isCurrent
            ? 'var(--ant-color-primary-bg)'
            : c.pinned
              ? 'var(--ant-color-warning-bg)'
              : undefined,
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          {isEditing ? (
            <Input
              autoFocus
              size="small"
              value={draft}
              maxLength={64}
              onChange={(e) => setDraft(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              onPressEnter={() => commitEdit(c.id)}
              onBlur={() => commitEdit(c.id)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setEditingId(null)
              }}
            />
          ) : (
            <>
              <div
                style={{
                  fontSize: 13,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title="双击重命名"
                onDoubleClick={(e) => {
                  e.stopPropagation()
                  startEdit(c)
                }}
              >
                {highlight(displayTitle)}
              </div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {fmtTime(c.updated_at)}
              </Typography.Text>
            </>
          )}
        </div>
        <span className="chat-actions">
          <Button
            type="text"
            size="small"
            icon={<PushpinOutlined style={c.pinned ? { color: 'var(--ant-color-warning)' } : undefined} />}
            title={c.pinned ? '取消置顶' : '置顶'}
            onClick={(e) => {
              e.stopPropagation()
              onTogglePin(c.id)
            }}
          />
          <Popconfirm
            title="确认删除该会话？"
            description="删除后不再显示。"
            onConfirm={(e) => {
              e?.stopPropagation()
              onRemove(c.id)
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
        </span>
      </div>
    )
  }

  const renderGroup = (title: string, items: AIConversationItem[]) => {
    if (!items.length) return null
    return (
      <div key={title} style={{ marginBottom: 4 }}>
        <Typography.Text
          type="secondary"
          style={{
            display: 'block',
            fontSize: 12,
            padding: '4px 10px 2px',
            color: 'var(--ant-color-text-tertiary)',
          }}
        >
          {title}
        </Typography.Text>
        {items.map(renderItem)}
      </div>
    )
  }

  const hasResult =
    visible.pinned.length > 0 || GROUP_ORDER.some((g) => (visible.buckets.get(g)?.length ?? 0) > 0)

  return (
    <div
      style={{
        width: 260,
        background: 'var(--ant-color-bg-container)',
        borderRadius: 8,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Button type="primary" icon={<PlusOutlined />} block onClick={onNew}>
        新建会话
      </Button>
      <Input.Search
        allowClear
        placeholder="搜索会话"
        value={searchInput}
        onChange={(e) => setSearchInput(e.target.value)}
        style={{ marginTop: 10 }}
      />
      <div style={{ flex: 1, overflowY: 'auto', marginTop: 10 }}>
        {hasResult ? (
          <>
            {renderGroup('置顶', visible.pinned)}
            {GROUP_ORDER.map((g) => renderGroup(g, visible.buckets.get(g) ?? []))}
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 24, color: 'var(--ant-color-text-tertiary)' }}>
            {keyword ? '未找到匹配的会话' : '暂无会话'}
          </div>
        )}
        {conversations.length < convTotal && (
          <Button type="link" size="small" block onClick={onLoadMore}>
            加载更多
          </Button>
        )}
      </div>
    </div>
  )
}
