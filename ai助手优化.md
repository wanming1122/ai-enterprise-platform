# AI 助手页面优化计划

> 基于当前 `frontend/src/views/ai/chat/index.tsx`（631行单文件组件）的全面优化方案。
> 按 **交互体验 → 会话管理 → 对话体验 → 代码质量** 四个维度分阶段推进。

---

## 一、UI / 交互体验优化

### 1.1 欢迎页推荐问题卡片
**现状：** 空会话只显示"你好，xxx"一行文字，用户不知道能做什么。

**方案：**
- 空态下展示 3×2 共 6 张推荐问题卡片，按场景分组：
  - 🔍 知识库类：「公司的年假制度是什么？」「入职需要准备哪些材料？」
  - 📊 数据类：「查一下本月库存不足的产品」
  - 🖼️ 图片类：「识别这张图片中的内容」
- 卡片点击后自动填入输入框并触发发送
- 卡片内容从后端系统配置读取（`ai_chat_followups` 表，复用现有 M7 配置化机制），空态兜底用前端常量

### 1.2 代码块复制按钮
**现状：** `MarkdownText` 只做了横向滚动，没有复制按钮。

**方案：**
- `MarkdownText.tsx` 增加 `components.code` 覆盖，渲染时在代码块右上角加 `<CopyOutlined>` 按钮
- 点击后调用 `navigator.clipboard.writeText(code)`，成功后按钮变 `CheckOutlined` 1.5 秒恢复
- 支持显示语言标签（如 `python`、`sql`、`bash`），从 `className="language-xxx"` 提取

### 1.3 消息操作栏
**现状：** 消息渲染后没有任何交互操作。

**方案：**
- 助手消息右下角悬停显示操作栏（Hover 才出现）：
  - 📋 **复制**：一键复制 Markdown 源文本
  - 🔄 **重新生成**：在同一次对话中重新发送上一条用户问题（新会话）
- 用户消息：
  - 📋 **复制**：一键复制文本
  - ✏️ **编辑**：点击后消息气泡变为 `TextArea` 可编辑，确认后替换原文并重新发送

### 1.4 流式打字体验优化
**现状：** 流式中光标字符 `▍` 直接拼在 Markdown 末尾，大段文本时闪烁明显。

**方案：**
- 光标改为独立的 CSS 动画元素（竖线闪烁），不拼进 Markdown 内容
- 流式到达时自动滚动到底部（现有逻辑保留，但 `smooth` 行为改为 `instant` 避免抖动）

---

## 二、会话管理优化

### 2.1 会话搜索
**现状：** 会话列表只有分页加载（每页 20 条），无搜索能力。

**方案：**
- 会话列表顶部新增搜索框（`Input.Search`），按标题关键词过滤
- 前端过滤（会话量不大，全量在内存中），输入防抖 300ms
- 搜索时高亮匹配的标题文本

### 2.2 会话重命名
**现状：** 会话标题自动取用户首条消息前 32 字，无法修改。

**方案：**
- 会话列表项双击标题进入编辑模式（`Input` 替换 `div`），回车或失焦保存
- 后端新增 `PATCH /ai/conversations/{id}` 接口更新 `title`
- 前端乐观更新（先改列表，后端失败再回滚）

### 2.3 会话置顶
**方案：**
- 会话列表项右侧 hover 显示📌置顶按钮
- 后端复用 `ai_conversation.pinned` 字段（M7 已有），前端列表排序 pinned=true 优先
- 置顶会话用淡金色背景区分

### 2.4 时间分组
**方案：**
- 会话列表按时间自动分组：「今天」「昨天」「近 7 天」「更早」
- 每组显示灰色分隔标签，视觉上更清晰

---

## 三、对话体验优化

### 3.1 Markdown 代码高亮增强
**现状：** 代码块无语法高亮，只有横向滚动。

**方案：**
- 引入 `react-syntax-highlighter`（或轻量的 `highlight.js`），按语言着色
- 代码块左上角显示语言标签（如 `python`）
- 右上角显示复制按钮（与 1.2 合并实现）
- 长代码块限制最大高度 400px + 内部滚动，避免撑爆页面

### 3.2 引用来源可点击
**现状：** 引用以 `Tag` 展示，Tooltip 显示 snippet，但无法跳转到知识库文件详情。

**方案：**
- 引用 Tag 改为可点击链接，hover 时显示 snippet + 相似度
- 点击后在右侧打开 `Drawer` 展示：文件名、标题路径、页码、片段内容、相似度条
- Drawer 底部加「查看完整文件」按钮，跳转到知识库文件管理页

### 3.3 思考过程交互优化
**现状：** 深度思考以 `Collapse` 折叠面板展示，流式中内容持续增长，面板自动撑高。

**方案：**
- 流式过程中思考面板默认**展开**，实时看到思考内容
- 流式结束后自动**收起**，只保留标题行（思考持续 Xs）
- 收起状态显示思考时长（如「思考了 3.2 秒」）
- 手动点击可随时展开/收起

### 3.4 空态引导与快捷操作
**方案：**
- 输入框 placeholder 轮播展示示例问题（每 5 秒切换一条）
- 输入框上方显示快捷提示标签：「问知识库」「查产品数据」「服务器状态」，点击自动填入对应前缀

### 3.5 错误处理增强
**现状：** 流式中断只显示 `message.error(msg)`。

**方案：**
- 错误消息内嵌「重试」按钮，点击自动重新发送上一条问题
- 流式中断的助手消息标记 `error` 状态，显示红色边框 + 重试按钮
- 区分「用户取消」和「服务端错误」：取消只显示「已停止」，错误显示错误信息

---

## 四、代码质量重构

### 4.1 组件拆分（631行 → 5个文件）

**目标：** 将 `chat/index.tsx` 拆分为以下结构：

```
views/ai/chat/
├── index.tsx              # 页面容器（~80行）：布局 + 组合子组件
├── useChat.ts             # 自定义 Hook（~200行）：所有对话状态和 SSE 逻辑
├── ConversationSidebar.tsx # 会话侧边栏（~120行）：列表 + 搜索 + 重命名 + 置顶
├── MessageItem.tsx         # 单条消息渲染（~150行）：用户/助手消息 + 工具标签 + 引用 + 思考
├── ChatInput.tsx           # 输入区域（~80行）：TextArea + 图片 + 发送/停止
└── WelcomePanel.tsx        # 欢迎面板（~60行）：推荐问题卡片
```

### 4.2 提取 useChat Hook

从当前组件中提取的核心逻辑：

```typescript
// useChat.ts
function useChat() {
  // --- 状态 ---
  conversations, convTotal, convPage      // 会话列表
  currentConvId, messages                  // 当前会话
  input, setInput                          // 输入
  streaming, deepThinking, pendingImages   // UI 状态
  abortRef                                // AbortController

  // --- 操作 ---
  loadConversations(page)     // 加载会话列表
  newConversation()           // 新建会话
  openConversation(id)        // 打开会话（含 tool 消息合并逻辑）
  removeConversation(id)      // 删除会话
  send()                      // 发送消息（SSE 流式）
  stop()                      // 中断生成
  handlePickImage(file)       // 图片选择压缩

  return {
    conversations, convTotal, convPage,
    currentConvId, messages, input, setInput,
    streaming, deepThinking, setDeepThinking,
    pendingImages,
    loadConversations, newConversation, openConversation,
    removeConversation, send, stop, handlePickImage,
  }
}
```

### 4.3 提取公共 SSE 函数

**现状：** `streamAIChat`（aiChat.ts）和 `streamKBChat`（kb.ts）有大量重复的 fetch + ReadableStream + 401 刷新 + 缓冲区解析逻辑。

**方案：** 新建 `api/sse.ts`，提取公共基座：

```typescript
// api/sse.ts
export async function fetchSSE(
  url: string,
  body: unknown,
  handlers: Record<string, (data: any) => void>,
  signal?: AbortSignal,
): Promise<void>
```

`streamAIChat` 和 `streamKBChat` 各自只定义自己的 payload 和 event 映射，不再重复实现底层流式解析。

### 4.4 AI 助手与知识库问答页公共组件复用

两个页面高度相似的部分：

| 公共部分 | 当前状态 | 提取方案 |
|---------|---------|---------|
| 消息气泡渲染 | 两页各写一遍 | `MessageItem` 组件 |
| 会话侧边栏 | KB 页无此功能 | `ConversationSidebar`（KB 页可复用） |
| SSE 流式发送 | 两页各写一遍 | `api/sse.ts` 公共基座 |
| Markdown 渲染 | 已有 `MarkdownText` | 统一使用，增加代码高亮 |
| 思考指示器 | 已有 `ThinkingIndicator` | 已复用，无变化 |

### 4.5 测试覆盖

为提取出的 `useChat` hook 和核心纯函数补充单元测试：
- `useChat` 的 send/stop/openConversation 状态流转
- SSE 事件解析（现有 `parseSSEBlock` 已可测）
- 会话列表的搜索过滤逻辑

---

## 五、实施顺序（建议）

| 阶段 | 内容 | 预计工时 |
|------|------|---------|
| **阶段一：重构** | 组件拆分 + useChat Hook + SSE 公共基座 + 测试 | 中等 |
| **阶段二：交互** | 欢迎页推荐问题 + 代码块复制/高亮 + 消息操作栏 | 中等 |
| **阶段三：会话** | 搜索 + 重命名 + 置顶 + 时间分组 + 后端 PATCH 接口 | 小 |
| **阶段四：体验** | 思考过程优化 + 引用可点击 + 错误重试 + placeholder 轮播 | 小 |

> 建议先做阶段一（重构），后续三个阶段可以在干净的组件结构上独立推进，互不阻塞。

---

## 六、涉及的文件变更清单

### 新增文件
- `frontend/src/views/ai/chat/useChat.ts`
- `frontend/src/views/ai/chat/ConversationSidebar.tsx`
- `frontend/src/views/ai/chat/MessageItem.tsx`
- `frontend/src/views/ai/chat/ChatInput.tsx`
- `frontend/src/views/ai/chat/WelcomePanel.tsx`
- `frontend/src/api/sse.ts`

### 修改文件
- `frontend/src/views/ai/chat/index.tsx`（重写为容器组件）
- `frontend/src/components/MarkdownText.tsx`（增加代码块复制 + 语法高亮）
- `frontend/src/components/MarkdownText.css`（代码块样式增强）
- `frontend/src/api/aiChat.ts`（改用 sse.ts 公共基座）
- `frontend/src/api/kb.ts`（改用 sse.ts 公共基座）

### 后端新增接口（如需要）
- `PATCH /api/v1/ai/conversations/{id}` —— 会话重命名（title 字段）
- `GET /api/v1/ai/conversations` 增加 `keyword` 查询参数 —— 会话搜索
