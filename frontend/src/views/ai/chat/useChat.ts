/**
 * AI 助手对话 Hook（阶段一重构，逻辑自原单文件组件逐行等价迁移）。
 *
 * 承载全部对话状态与 SSE 流式逻辑，不含 DOM 副作用（输入区回车、消息滚动到底部等
 * 容器级交互由 index.tsx 负责）。拆分后 index.tsx 与各子组件通过返回对象消费数据与操作。
 */
import { App } from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  aiChatApi,
  streamAIChat,
  type AIConversationItem,
  type AIToolEvent,
} from '@/api/aiChat'
import type { Citation } from '@/api/kb'
import { compressToDataUrl } from '@/utils/image'

/** 页面内消息模型：历史加载与流式生成共用 */
export interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  /** 本次思考耗时（秒，浮点保留 1 位）；结束后用于「思考了 Xs」展示 */
  reasoningSeconds?: number
  /** 服务端/网络错误：气泡标红并展示 errorText + 重试 */
  error?: boolean
  errorText?: string
  tools?: AIToolEvent[]
  citations?: Citation[]
  attachments?: { type: string; url: string }[]
  streaming?: boolean
  /** 用户主动停止：仅展示「已停止生成」，不视为错误 */
  stopped?: boolean
}

export function useChat() {
  const { message } = App.useApp()

  const [conversations, setConversations] = useState<AIConversationItem[]>([])
  const [convTotal, setConvTotal] = useState(0)
  const [convPage, setConvPage] = useState(1)
  const [currentConvId, setCurrentConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [deepThinking, setDeepThinking] = useState(false)
  const [pendingImages, setPendingImages] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const loadConversations = useCallback(async (p: number) => {
    const res = await aiChatApi.conversations({ page: p, page_size: 20 })
    setConversations((prev) => (p === 1 ? res.list : [...prev, ...res.list]))
    setConvTotal(res.total)
    setConvPage(p)
  }, [])

  useEffect(() => {
    loadConversations(1)
  }, [loadConversations])

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
        list.push({ role: 'user', content: m.content, attachments: m.attachments ?? undefined })
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

  const send = async (questionOverride?: string) => {
    const question = (questionOverride ?? input).trim()
    if (!question || streaming) return
    setInput('')
    setStreaming(true)
    const images = pendingImages
    setPendingImages([])
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: question,
        attachments: images.map((url) => ({ type: 'image', url })),
      },
      { role: 'assistant', content: '', tools: [], citations: [], streaming: true },
    ])

    const controller = new AbortController()
    abortRef.current = controller
    let answer = ''
    let reasoning = ''
    let tools: AIToolEvent[] = []
    let reasoningStartedAt: number | null = null

    /** 生成结束统一收尾：停止流式，并附带思考时长（有思考过程才记录） */
    const finishAssistant = (patch: Partial<ChatMsg>) => {
      const seconds =
        reasoningStartedAt !== null && reasoning
          ? Number(((Date.now() - reasoningStartedAt) / 1000).toFixed(1))
          : undefined
      patchAssistant({
        streaming: false,
        ...(seconds !== undefined ? { reasoningSeconds: seconds } : {}),
        ...patch,
      })
    }

    try {
      await streamAIChat(
        { question, conversation_id: currentConvId, deep_thinking: deepThinking, images },
        {
          onMeta: ({ conversation_id }) => {
            if (currentConvId == null) {
              setCurrentConvId(conversation_id)
              setConversations((prev) => [
                {
                  id: conversation_id,
                  title: question.slice(0, 32),
                  pinned: false,
                  created_at: '',
                  updated_at: '',
                },
                ...prev,
              ])
            }
          },
          onTool: (ev) => {
            tools = [...tools, ev]
            patchAssistant({ tools })
          },
          onReasoning: (delta) => {
            if (reasoningStartedAt === null) reasoningStartedAt = Date.now()
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
            finishAssistant({})
            loadConversations(1)
          },
          onError: (msg) => {
            // 服务端 error 事件 / HTTP 错误：标红并内嵌错误信息（不再叠加全局 toast）
            finishAssistant({ error: true, errorText: msg })
            if (!answer) setPendingImages(images)
          },
        },
        controller.signal,
      )
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') {
        // 用户主动停止：仅标记停止，不视为错误
        finishAssistant({ stopped: true })
      } else {
        // 网络异常 / 401 刷新失败等：标红展示错误
        finishAssistant({ error: true, errorText: '网络异常，请稍后重试' })
      }
      if (!answer) setPendingImages(images)
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const stop = () => {
    abortRef.current?.abort()
  }

  /**
   * 重新生成当前会话最后一轮：截断到最后一条用户提问（含其回答一并移除）后，
   * 以该提问内容重发，形成新一轮问答（服务端消息为追加式，旧问答对仅本地移除）。
   */
  const regenerate = () => {
    if (streaming) {
      message.warning('请先停止当前生成')
      return
    }
    let userIndex = -1
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userIndex = i
        break
      }
    }
    if (userIndex < 0) return
    const text = messages[userIndex].content.trim()
    if (!text) return
    setMessages((prev) => prev.slice(0, userIndex))
    void send(text)
  }

  /** 会话重命名（乐观更新，失败回滚） */
  const renameConversation = async (id: number, title: string) => {
    const snapshot = conversations.find((c) => c.id === id)
    if (!snapshot) return
    const trimmed = title.trim()
    if (!trimmed) {
      message.warning('标题不能为空')
      return
    }
    setConversations((list) => list.map((c) => (c.id === id ? { ...c, title: trimmed } : c)))
    try {
      await aiChatApi.rename(id, trimmed)
    } catch {
      setConversations((list) => list.map((c) => (c.id === id ? { ...c, title: snapshot.title } : c)))
      message.error('重命名失败')
    }
  }

  /** 会话置顶切换（乐观更新，成功后再拉取列表对齐服务端排序） */
  const togglePin = async (id: number) => {
    const snapshot = conversations.find((c) => c.id === id)
    if (!snapshot) return
    const next = !snapshot.pinned
    setConversations((list) => list.map((c) => (c.id === id ? { ...c, pinned: next } : c)))
    try {
      await aiChatApi.setPinned(id, next)
      loadConversations(1)
    } catch {
      setConversations((list) => list.map((c) => (c.id === id ? { ...c, pinned: snapshot.pinned } : c)))
      message.error('置顶操作失败')
    }
  }

  /** 编辑最后一条用户提问（内容覆盖）后重发，形成新一轮问答 */
  const editLastUser = (newText: string) => {
    if (streaming) {
      message.warning('请先停止当前生成')
      return
    }
    const text = newText.trim()
    if (!text) {
      message.warning('提问内容不能为空')
      return
    }
    let userIndex = -1
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userIndex = i
        break
      }
    }
    if (userIndex < 0) return
    setMessages((prev) => prev.slice(0, userIndex))
    void send(text)
  }

  /** 选图：压缩为 Data URL（最长边 1568），最多 3 张随问发送 */
  const handlePickImage = async (file: File) => {
    if (pendingImages.length >= 3) {
      message.warning('每次最多附带 3 张图片')
      return false
    }
    try {
      const dataUrl = await compressToDataUrl(file, 1568, 0.85)
      setPendingImages((prev) => [...prev, dataUrl])
    } catch {
      message.error('图片处理失败')
    }
    return false
  }

  return {
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
    abortRef,
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
  }
}
