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
  type AIChatStats,
  type AIConversationItem,
  type AIModelOption,
  type AIToolEvent,
  type ContextUsage,
} from '@/api/aiChat'
import { profileApi } from '@/api/profile'
import { useUserStore } from '@/stores/user'
import type { Citation } from '@/api/kb'
import { compressToDataUrl } from '@/utils/image'

/** 错误类型常量 */
export const ErrorType = {
  NETWORK: 'network',      // 网络错误
  TIMEOUT: 'timeout',      // 超时错误
  AUTH: 'auth',            // 认证错误
  SERVER: 'server',        // 服务端错误
  ABORT: 'abort',          // 用户主动停止
  UNKNOWN: 'unknown',      // 未知错误
} as const

export type ErrorType = typeof ErrorType[keyof typeof ErrorType]

/** 错误类型对应的提示文案和操作建议 */
export const ERROR_MESSAGES: Record<ErrorType, { text: string; action?: string }> = {
  [ErrorType.NETWORK]: {
    text: '网络连接已断开，请检查网络后重试',
    action: '点击"重新发送"重试',
  },
  [ErrorType.TIMEOUT]: {
    text: '响应超时，服务器可能正忙',
    action: '请稍后重试或联系管理员',
  },
  [ErrorType.AUTH]: {
    text: '登录已过期',
    action: '请重新登录',
  },
  [ErrorType.SERVER]: {
    text: '服务器内部错误',
    action: '请稍后重试或联系管理员',
  },
  [ErrorType.ABORT]: {
    text: '已停止生成',
  },
  [ErrorType.UNKNOWN]: {
    text: '发生未知错误',
    action: '请稍后重试',
  },
}

/** 根据错误对象分类错误类型 */
function classifyError(error: any): ErrorType {
  if (error?.name === 'AbortError') return ErrorType.ABORT

  // 网络错误：fetch 失败、TypeError 等
  if (error instanceof TypeError && error.message?.includes('fetch')) {
    return ErrorType.NETWORK
  }
  if (error?.message?.includes('Failed to fetch') || error?.message?.includes('NetworkError')) {
    return ErrorType.NETWORK
  }

  // 超时错误
  if (error?.message?.includes('timeout') || error?.code === 'ECONNABORTED' ||
      error?.message?.includes('Timeout') || error?.message?.includes('timed out')) {
    return ErrorType.TIMEOUT
  }

  // 认证错误
  if (error?.status === 401 || error?.status === 403) {
    return ErrorType.AUTH
  }

  // 服务端错误
  if (error?.status >= 500) {
    return ErrorType.SERVER
  }

  return ErrorType.UNKNOWN
}

/** 页面内消息模型：历史加载与流式生成共用 */
export interface ChatMsg {
  /** 稳定 id：服务端消息用 s{id}，本地新增用 local 自增（React key 用） */
  id: string
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  /** 本次思考耗时（秒，浮点保留 1 位）；结束后用于「思考了 Xs」展示 */
  reasoningSeconds?: number
  /** 服务端/网络错误：气泡标红并展示 errorText + 重试 */
  error?: boolean
  errorText?: string
  /** 错误类型，用于区分不同的错误展示方式 */
  errorType?: ErrorType
  /** 错误操作建议 */
  errorAction?: string
  tools?: AIToolEvent[]
  citations?: Citation[]
  attachments?: { type: string; url: string }[]
  streaming?: boolean
  /** 用户主动停止：仅展示「已停止生成」，不视为错误 */
  stopped?: boolean
  /** 本轮注入的长期记忆条数（召回命中>0 才有） */
  memoryCount?: number
  /** 本轮用量统计（耗时/token/上下文占用） */
  stats?: AIChatStats
}

/** 前端 token 启发式估算（与后端 estimate_tokens 同口径）：CJK≈1字/token，其余≈4字符/token。
 *  图片附件不参与估算（视觉 token 计费因模型而异，字符数换算会严重失真）。 */
function estimateTokens(text: string): number {
  if (!text) return 0
  let cjk = 0
  for (const ch of text) if (ch >= '\u4e00' && ch <= '\u9fff') cjk++
  return cjk + Math.ceil((text.length - cjk) / 4)
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
  /** 当前会话上下文占用明细（最近一轮 done 下发，供输入区圆环悬停浮层展示） */
  const [contextUsage, setContextUsage] = useState<ContextUsage | null>(null)
  /** 启用中的生成模型与当前选择（空 = 后端默认模型） */
  const [models, setModels] = useState<AIModelOption[]>([])
  const [currentModelId, setCurrentModelId] = useState<number | null>(null)
  /** 长会话分页：是否有更早消息 */
  const [hasMoreMessages, setHasMoreMessages] = useState(false)
  /** SSE 状态提示：已收到 meta（连接建立）；超 15s 无增量置 slow */
  const [connected, setConnected] = useState(false)
  const [slow, setSlow] = useState(false)
  const slowTimerRef = useRef<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const uidRef = useRef(0)
  const nextLocalId = () => `local-${++uidRef.current}`
  /** 打开历史会话时由 openConversation 注入「加载更早消息」实现，供稳定回调调用 */
  const loadOlderRef = useRef<() => void>(() => {})
  /** 长会话分页游标：当前已加载的最旧服务端消息 id（null=无可加载的更早消息） */
  const oldestServerIdRef = useRef<number | null>(null)
  const loadingOlderRef = useRef(false)
  /** 稳定回调读取的最新状态（避免 memo 组件因回调身份变化而整体失效） */
  const stateRef = useRef({ messages, streaming, currentConvId })
  stateRef.current = { messages, streaming, currentConvId }
  const sendRef = useRef<((q?: string) => Promise<void>) | null>(null)
  const loadOlderMessages = useCallback(() => loadOlderRef.current(), [])

  // 页面卸载时中止进行中的 SSE 流：停止后台 token 消耗，避免卸载后回调继续 setState
  useEffect(() => () => abortRef.current?.abort(), [])

  const bumpSlowTimer = () => {
    if (slowTimerRef.current) window.clearTimeout(slowTimerRef.current)
    slowTimerRef.current = window.setTimeout(() => setSlow(true), 15000)
  }
  const clearSlowTimer = () => {
    if (slowTimerRef.current) window.clearTimeout(slowTimerRef.current)
    slowTimerRef.current = null
  }

  // 模型列表初始化：拉取启用模型，选中用户偏好（default_model），无效则回退默认模型；
  // 同时用该模型的窗口初始化圆环（进入页面即可见，used=0 待首轮统计校准）
  useEffect(() => {
    aiChatApi
      .models()
      .then((list) => {
        setModels(list)
        const pref = useUserStore.getState().userInfo?.preferences?.default_model
        const initial = (pref && list.find((m) => m.id === pref)) || list.find((m) => m.is_default) || list[0]
        if (pref && list.some((m) => m.id === pref)) setCurrentModelId(pref)
        if (initial?.context_window) {
          setContextUsage((prev) =>
            prev ?? { used: 0, total: initial.context_window!, breakdown: [], cacheHitRate: null },
          )
        }
      })
      .catch(() => setModels([]))  // 拉取失败静默降级：隐藏下拉，走后端默认模型
  }, [])

  /** 切换模型：记录选择并持久化到用户偏好（失败不阻塞，仅本次会话生效）；
   *  同时把圆环窗口切换为新模型的真实窗口（旧统计沿用，占比自动重算） */
  const changeModel = (id: number) => {
    setCurrentModelId(id)
    const target = models.find((m) => m.id === id)
    if (target?.context_window) {
      setContextUsage((prev) =>
        prev
          ? { ...prev, total: target.context_window! }
          : { used: 0, total: target.context_window!, breakdown: [], cacheHitRate: null },
      )
    }
    profileApi
      .updatePreferences({ default_model: id })
      .then((preferences) => {
        const userInfo = useUserStore.getState().userInfo
        if (userInfo) useUserStore.getState().updateUserInfo({ ...userInfo, preferences })
      })
      .catch(() => {})
  }

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
    oldestServerIdRef.current = null
  }

  const openConversation = async (id: number) => {
    if (streaming) {
      message.warning('请先停止当前生成')
      return
    }
    const detail = await aiChatApi.conversation(id)
    setCurrentConvId(id)
    // 打开历史会话：优先用后端同口径估算（最近4轮+系统提示词+工具定义+工具结果，不含记忆注入）；
    // 后端未返回时退回本地消息正文估算。下一轮 done 事件会用真实统计覆盖
    const historyUsed = detail.messages.reduce(
      (sum, m) => sum + estimateTokens(m.content || ''),
      0,
    )
    // tool 消息附着到 assistant 消息上以标签展示（兼容 tool 在前/在后两种落库顺序）
    const list: ChatMsg[] = []
    let pendingTools: AIToolEvent[] = []
    for (const m of detail.messages) {
      if (m.role === 'user') {
        list.push({ id: `s${m.id}`, role: 'user', content: m.content, attachments: m.attachments ?? undefined })
      } else if (m.role === 'tool') {
        pendingTools.push({ tool: m.tool_name ?? '' })
      } else {
        list.push({
          id: `s${m.id}`,
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
    setHasMoreMessages(detail.has_more)
    // 分页游标：当前已加载的最旧服务端消息 id（供「加载更早」作为 before_id）
    const serverIds = list.filter((m) => m.id.startsWith('s')).map((m) => Number(m.id.slice(1)))
    oldestServerIdRef.current = serverIds.length ? Math.min(...serverIds) : null
    setContextUsage((prev) => {
      const win =
        (prev && prev.total > 0 ? prev.total : undefined) ??
        models.find((m) => m.id === (currentModelId ?? -1))?.context_window
      if (!win) return prev
      const backend = detail.context_usage
      if (backend && backend.total > 0) {
        return { used: backend.total, total: win, breakdown: backend.breakdown, cacheHitRate: null }
      }
      return {
        used: historyUsed,
        total: win,
        breakdown: historyUsed > 0 ? [{ label: '历史消息', tokens: historyUsed }] : [],
        cacheHitRate: null,
      }
    })

    /** 加载更早的历史消息（长会话分页）：游标取「当前已加载的最旧服务端消息 id」并
     *  在每次加载后推进，避免重复拉取同一批；会话 id 用本次打开的参数 id，
     *  避免闭包捕获到切换前的旧 currentConvId。 */
    const loadOlderMessages = async () => {
      const firstId = oldestServerIdRef.current
      if (!id || !firstId || loadingOlderRef.current) return
      loadingOlderRef.current = true
      try {
        const res = await aiChatApi.listMessages(id, firstId)
        if (!res.messages.length) {
          setHasMoreMessages(false)
          return
        }
        const older: ChatMsg[] = []
        let olderTools: AIToolEvent[] = []
        for (const m of res.messages) {
          if (m.role === 'user') {
            older.push({ id: `s${m.id}`, role: 'user', content: m.content, attachments: m.attachments ?? undefined })
          } else if (m.role === 'tool') {
            olderTools.push({ tool: m.tool_name ?? '' })
          } else {
            older.push({
              id: `s${m.id}`, role: 'assistant', content: m.content,
              reasoning: m.reasoning_content ?? undefined,
              tools: olderTools.length ? olderTools : undefined,
              citations: m.citations ?? undefined,
            })
            olderTools = []
          }
        }
        const ids = res.messages.map((m) => m.id)
        oldestServerIdRef.current = Math.min(...ids, firstId)
        setHasMoreMessages(res.has_more)
        setMessages((prev) => [...older, ...prev])
      } catch {
        // 错误已由拦截器统一提示
      } finally {
        loadingOlderRef.current = false
      }
    }
    loadOlderRef.current = loadOlderMessages
  }

  const removeConversation = async (id: number) => {
    await aiChatApi.removeConversation(id)
    message.success('会话已删除')
    // 用 stateRef 读最新值：闭包里的 currentConvId 可能已因快速切换而过期，误清空新会话
    if (stateRef.current.currentConvId === id) newConversation()
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
    const question = (typeof questionOverride === 'string' ? questionOverride : input).trim()
    if (!question || streaming) return
    setInput('')
    setStreaming(true)
    const images = pendingImages
    setPendingImages([])
    setMessages((prev) => [
      ...prev,
      {
        id: nextLocalId(),
        role: 'user',
        content: question,
        attachments: images.map((url) => ({ type: 'image', url })),
      },
      { id: nextLocalId(), role: 'assistant', content: '', tools: [], citations: [], streaming: true },
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
        {
          question,
          conversation_id: currentConvId,
          deep_thinking: deepThinking,
          images,
          model_id: currentModelId ?? undefined,
        },
        {
          onMeta: ({ conversation_id }) => {
            setConnected(true)
            bumpSlowTimer()
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
            bumpSlowTimer()
            if (reasoningStartedAt === null) reasoningStartedAt = Date.now()
            reasoning += delta
            patchAssistant({ reasoning })
          },
          onMessage: (delta) => {
            bumpSlowTimer()
            answer += delta
            patchAssistant({ content: answer })
          },
          onCitations: (list) => {
            patchAssistant({ citations: list })
          },
          onMemory: (data) => {
            if (data.count > 0) patchAssistant({ memoryCount: data.count })
          },
          onDone: (data) => {
            clearSlowTimer()
            setConnected(false)
            if (
              data.usage &&
              data.duration_ms != null &&
              data.context_tokens != null &&
              data.context_window != null
            ) {
              const stats: AIChatStats = {
                duration_ms: data.duration_ms,
                prompt_tokens: data.usage.prompt_tokens,
                completion_tokens: data.usage.completion_tokens,
                total_tokens: data.usage.total_tokens,
                estimated: data.usage.estimated,
                context_tokens: data.context_tokens,
                context_window: data.context_window,
                context_breakdown: data.context_breakdown ?? [],
              }
              patchAssistant({ stats })
              setContextUsage({
                used: stats.context_tokens,
                total: stats.context_window,
                breakdown: stats.context_breakdown,
                cacheHitRate: data.cache_hit_rate ?? null,
              })
            }
            finishAssistant({})
            loadConversations(1)
          },
          onError: (msg) => {
            // 服务端 error 事件 / HTTP 错误：标红并内嵌错误信息（不再叠加全局 toast）
            const errorType = classifyError({ message: msg })
            const errorInfo = ERROR_MESSAGES[errorType]
            finishAssistant({
              error: true,
              errorText: errorInfo.text,
              errorType,
              errorAction: errorInfo.action,
            })
            if (!answer) setPendingImages(images)
          },
        },
        controller.signal,
      )
    } catch (e) {
      const errorType = classifyError(e)
      const errorInfo = ERROR_MESSAGES[errorType]

      if (errorType === ErrorType.ABORT) {
        // 用户主动停止：仅标记停止，不视为错误
        finishAssistant({ stopped: true })
      } else if (errorType === ErrorType.AUTH) {
        // 认证错误：提示并让全局拦截器处理跳转
        finishAssistant({
          error: true,
          errorText: errorInfo.text,
          errorType,
          errorAction: errorInfo.action,
        })
      } else {
        // 其他错误：标红展示错误信息和操作建议
        finishAssistant({
          error: true,
          errorText: errorInfo.text,
          errorType,
          errorAction: errorInfo.action,
        })
      }
      if (!answer) setPendingImages(images)
    } finally {
      setStreaming(false)
      setConnected(false)
      setSlow(false)
      clearSlowTimer()
      abortRef.current = null
    }
  }
  sendRef.current = send

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  /**
   * 重新生成当前会话最后一轮：截断到最后一条用户提问（含其回答一并移除）后，
   * 以该提问内容重发，形成新一轮问答（服务端消息为追加式，旧问答对仅本地移除）。
   * 通过 stateRef 读取最新状态 + 稳定引用，供 memo 化的 MessageItem 使用。
   */
  const regenerate = useCallback(() => {
    const { messages: msgs, streaming: busy } = stateRef.current
    if (busy) {
      message.warning('请先停止当前生成')
      return
    }
    let userIndex = -1
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        userIndex = i
        break
      }
    }
    if (userIndex < 0) return
    const text = msgs[userIndex].content.trim()
    if (!text) return
    setMessages((prev) => prev.slice(0, userIndex))
    void sendRef.current?.(text)
  }, [message])

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

  /**
   * 编辑指定用户提问（内容覆盖后重发）：截断该条及其后全部消息，以新内容重发，
   * 形成新一轮问答（服务端消息为追加式，被截断部分仅本地移除）。
   */
  const editUserMessage = useCallback((index: number, newText: string) => {
    const { messages: msgs, streaming: busy } = stateRef.current
    if (busy) {
      message.warning('请先停止当前生成')
      return
    }
    const text = newText.trim()
    if (!text) {
      message.warning('提问内容不能为空')
      return
    }
    if (index < 0 || index >= msgs.length || msgs[index].role !== 'user') return
    setMessages((prev) => prev.slice(0, index))
    void sendRef.current?.(text)
  }, [message])

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
    contextUsage,
    models,
    currentModelId,
    changeModel,
    hasMoreMessages,
    loadOlderMessages,
    connected,
    slow,
    abortRef,
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
  }
}
