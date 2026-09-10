/**
 * AI 助手页面容器（阶段一重构后）：只负责双栏布局与组合 useChat/子组件，
 * 对话状态与 SSE 逻辑在 useChat.ts，各区域渲染在 ConversationSidebar/MessageItem/
 * ChatInput/WelcomePanel。渲染结构与原单文件版本保持一致。
 */
import { useEffect, useRef, useState } from 'react'
import { Badge, Button, Skeleton, Space, Typography } from 'antd'
import { DownOutlined, MenuOutlined, ReloadOutlined, ScheduleOutlined } from '@ant-design/icons'
import { useUserStore } from '@/stores/user'
import ChatInput from './ChatInput'
import ConversationSidebar from './ConversationSidebar'
import MemoryDrawer from './MemoryDrawer'
import MessageItem from './MessageItem'
import WelcomePanel from './WelcomePanel'
import { useChat } from './useChat'

export default function AIChat() {
  const userInfo = useUserStore((s) => s.userInfo)
  const {
    conversations,
    convTotal,
    convPage,
    currentConvId,
    messages,
    input,
    setInput,
    streaming,
    deepThinking,
    setDeepThinking,
    pendingImages,
    setPendingImages,
    contextUsage,
    models,
    currentModelId,
    changeModel,
    loadConversations,
    newConversation,
    openConversation,
    removeConversation,
    send,
    stop,
    handlePickImage,
    regenerate,
    editUserMessage,
    renameConversation,
    togglePin,
    hasMoreMessages,
    loadOlderMessages,
    loadingConversation,
    connected,
    slow,
  } = useChat()

  const listRef = useRef<HTMLDivElement | null>(null)
  /** 窄屏适配：<1024px 时侧栏改为抽屉式覆盖层 */
  const [narrow, setNarrow] = useState(window.innerWidth < 1024)
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 1024)
  const [memoryOpen, setMemoryOpen] = useState(false)

  /** 滚动跟随：仅当用户处于底部时才自动吸底；上滑查看历史时不打断，改为提示新内容 */
  const atBottomRef = useRef(true)
  const [showJump, setShowJump] = useState(false)
  const [unread, setUnread] = useState(false)

  /** 依据容器真实几何刷新滚动跟随状态。
   *  内容不足一屏（不可滚动）时不存在"是否在底部"的问题 → 一律视为在底部、隐藏「回到底部」。 */
  const syncScrollState = () => {
    const el = listRef.current
    if (!el) return
    const scrollable = el.scrollHeight - el.clientHeight > 4
    const near = !scrollable || el.scrollHeight - el.scrollTop - el.clientHeight < 80
    atBottomRef.current = near
    setShowJump((prev) => (prev === !near ? prev : !near))
    if (near) setUnread((prev) => (prev ? false : prev))
  }

  const scrollToBottom = () => {
    const el = listRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    atBottomRef.current = true
    setShowJump(false)
    setUnread(false)
  }

  useEffect(() => {
    const onResize = () => {
      const isNarrow = window.innerWidth < 1024
      setNarrow(isNarrow)
      setSidebarOpen(!isNarrow)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // 消息区尺寸变化（窗口缩放 / 输入框增高 / 侧栏折叠）会改变"是否可滚动"，
  // 用 ResizeObserver 自动纠正「回到底部」按钮显隐，避免状态与真实几何不一致
  useEffect(() => {
    const el = listRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => syncScrollState())
    ro.observe(el)
    return () => ro.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 消息变化后滚动：刚打开的历史长会话→滚到顶部（从头看）；用户已在底部→跟随到底部；
  // 用户上滑查看历史→不打断，仅标记有新内容（由「回到底部」按钮提示）
  const justOpenedConvRef = useRef(false)
  useEffect(() => {
    const el = listRef.current
    if (!el) return
    // 内容不足一屏时容器不可滚动、本就在底部：统一按"已在底部"处理，不显示「回到底部」
    const scrollable = el.scrollHeight - el.clientHeight > 4
    if (justOpenedConvRef.current) {
      justOpenedConvRef.current = false
      if (scrollable) {
        el.scrollTop = 0
        atBottomRef.current = false
        setShowJump(true)
        setUnread(false)
      } else {
        syncScrollState()
      }
      return
    }
    if (!scrollable) {
      syncScrollState()
      return
    }
    if (atBottomRef.current) {
      el.scrollTop = el.scrollHeight
    } else {
      // 用户正在上滑查看历史：不强制拉回底部，仅提示有新内容
      setUnread(true)
    }
  }, [messages])

  const currentTitle = conversations.find((c) => c.id === currentConvId)?.title

  // 消息操作入口：重新生成/重试仅对「对话末尾」的助手消息开放；每条用户提问均可编辑重发
  const lastIndex = messages.length - 1

  return (
    <div style={{ display: 'flex', gap: 12, height: '100%', position: 'relative' }}>
      {/* 左侧：会话列表（窄屏时为抽屉式覆盖层） */}
      {narrow && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 19 }}
        />
      )}
      <div
        style={
          narrow
            ? sidebarOpen
              ? { position: 'fixed', left: 12, top: 96, bottom: 12, width: 260, zIndex: 20 }
              : { display: 'none' }
            : { flexShrink: 0, height: '100%' }
        }
      >
        <ConversationSidebar
          conversations={conversations}
          convTotal={convTotal}
          currentConvId={currentConvId}
          onNew={() => {
            newConversation()
            atBottomRef.current = true
            setShowJump(false)
            setUnread(false)
          }}
          onOpen={(id) => {
            justOpenedConvRef.current = true
            setShowJump(false)
            setUnread(false)
            openConversation(id)
          }}
          onRemove={removeConversation}
          onLoadMore={() => loadConversations(convPage + 1)}
          onRename={renameConversation}
          onTogglePin={togglePin}
        />
      </div>

      {/* 右侧：对话区 */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          background: 'var(--ant-color-bg-container)',
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
            borderBottom: '1px solid var(--ant-color-split)',
            paddingBottom: 8,
            marginBottom: 8,
          }}
        >
          <Space size={12}>
            {narrow && (
              <Button icon={<MenuOutlined />} size="small" onClick={() => setSidebarOpen(true)} />
            )}
            <Typography.Text strong>
              {currentConvId ? currentTitle || `会话 #${currentConvId}` : '新会话'}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              企业管理场景对话入口
            </Typography.Text>
          </Space>
          <Space size={8}>
            <Button
              icon={<ScheduleOutlined />}
              size="small"
              onClick={() => setMemoryOpen(true)}
              title="查看并管理 AI 记住的关于你的信息"
            >
              记忆
            </Button>
            <Button icon={<ReloadOutlined />} size="small" onClick={() => loadConversations(1)}>
              刷新
            </Button>
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          <div
            ref={listRef}
            className="chat-scroll"
            onScroll={syncScrollState}
            style={{ height: '100%', overflowY: 'auto', padding: '4px 4px' }}
          >
            {loadingConversation ? (
              <div style={{ padding: '8px 4px' }}>
                <Skeleton active paragraph={{ rows: 6 }} />
              </div>
            ) : messages.length === 0 ? (
              <WelcomePanel
                name={userInfo?.nickname || userInfo?.username || '朋友'}
                onAsk={(text) => send(text)}
              />
            ) : (
            <>
              {hasMoreMessages && (
                <div style={{ textAlign: 'center', marginBottom: 8 }}>
                  <Button size="small" type="link" onClick={loadOlderMessages}>
                    加载更早的消息
                  </Button>
                </div>
              )}
              {messages.map((m, i) => (
                <MessageItem
                  key={m.id}
                  msg={m}
                  messageIndex={i}
                  showRegenerate={m.role === 'assistant' && i === lastIndex && !streaming && !m.error}
                  showRetry={m.role === 'assistant' && i === lastIndex && !streaming && !!m.error}
                  showEdit={m.role === 'user' && !streaming}
                  connected={connected}
                  slow={slow}
                  onRegenerate={regenerate}
                  onRetry={regenerate}
                  onEditMessage={editUserMessage}
                />
              ))}
            </>
          )}
          </div>
          {showJump && (
            <div style={{ position: 'absolute', right: 16, bottom: 16, zIndex: 5 }}>
              <Badge dot={unread} offset={[-2, 4]}>
                <Button
                  shape="circle"
                  type="primary"
                  icon={<DownOutlined />}
                  title="回到底部"
                  onClick={scrollToBottom}
                  style={{ boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)' }}
                />
              </Badge>
            </div>
          )}
        </div>

        <ChatInput
          input={input}
          streaming={streaming}
          currentConvId={currentConvId}
          pendingImages={pendingImages}
          deepThinking={deepThinking}
          onDeepThinkingChange={setDeepThinking}
          contextUsage={contextUsage}
          models={models}
          currentModelId={currentModelId}
          onModelChange={changeModel}
          onInputChange={setInput}
          onSend={send}
          onStop={stop}
          onPickImage={handlePickImage}
          onRemoveImage={(i) => setPendingImages((prev) => prev.filter((_, j) => j !== i))}
        />
      </div>

      {/* 长期记忆管理抽屉 */}
      <MemoryDrawer open={memoryOpen} onClose={() => setMemoryOpen(false)} />
    </div>
  )
}
