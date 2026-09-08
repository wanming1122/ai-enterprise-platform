/**
 * AI 助手页面容器（阶段一重构后）：只负责双栏布局与组合 useChat/子组件，
 * 对话状态与 SSE 逻辑在 useChat.ts，各区域渲染在 ConversationSidebar/MessageItem/
 * ChatInput/WelcomePanel。渲染结构与原单文件版本保持一致。
 */
import { useEffect, useRef } from 'react'
import { Button, Space, Switch, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useUserStore } from '@/stores/user'
import ChatInput from './ChatInput'
import ConversationSidebar from './ConversationSidebar'
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
    loadConversations,
    newConversation,
    openConversation,
    removeConversation,
    send,
    stop,
    handlePickImage,
    regenerate,
    editLastUser,
    renameConversation,
    togglePin,
  } = useChat()

  const listRef = useRef<HTMLDivElement | null>(null)

  // 消息变化（含流式增量）后滚动到底部
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const currentTitle = conversations.find((c) => c.id === currentConvId)?.title

  // 消息操作入口：仅对「对话末尾」的用户/助手消息开放重新生成与编辑，避免截断历史
  let lastUserIndex = -1
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user') {
      lastUserIndex = i
      break
    }
  }
  const lastIndex = messages.length - 1

  return (
    <div style={{ display: 'flex', gap: 12, height: 'calc(100vh - 96px)' }}>
      {/* 左侧：会话列表 */}
      <ConversationSidebar
        conversations={conversations}
        convTotal={convTotal}
        currentConvId={currentConvId}
        onNew={newConversation}
        onOpen={openConversation}
        onRemove={removeConversation}
        onLoadMore={() => loadConversations(convPage + 1)}
        onRename={renameConversation}
        onTogglePin={togglePin}
      />

      {/* 右侧：对话区 */}
      <div
        style={{
          flex: 1,
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
            <WelcomePanel
              name={userInfo?.nickname || userInfo?.username || '朋友'}
              onAsk={(text) => send(text)}
            />
          ) : (
            messages.map((m, i) => (
              <MessageItem
                key={i}
                msg={m}
                showRegenerate={m.role === 'assistant' && i === lastIndex && !streaming && !m.error}
                showRetry={m.role === 'assistant' && i === lastIndex && !streaming && !!m.error}
                showEdit={m.role === 'user' && i === lastUserIndex && !streaming}
                onRegenerate={regenerate}
                onRetry={regenerate}
                onEditMessage={editLastUser}
              />
            ))
          )}
        </div>

        <ChatInput
          input={input}
          streaming={streaming}
          currentConvId={currentConvId}
          pendingImages={pendingImages}
          onInputChange={setInput}
          onSend={send}
          onStop={stop}
          onPickImage={handlePickImage}
          onRemoveImage={(i) => setPendingImages((prev) => prev.filter((_, j) => j !== i))}
        />
      </div>
    </div>
  )
}
