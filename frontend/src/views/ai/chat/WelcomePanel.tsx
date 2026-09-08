/**
 * 空会话欢迎面板（AI 助手页）：问候语 + 场景分组推荐问题卡片。
 * 卡片内容暂为前端常量（文档所述 ai_chat_followups 配置化机制尚未落地，
 * 待后端配置能力就绪后切换为可配置数据源）。点击卡片直接发起提问。
 */
import { Typography } from 'antd'

interface Followup {
  icon: string
  category: string
  text: string
}

const FOLLOWUPS: Followup[] = [
  { icon: '🔍', category: '知识库', text: '公司的年假制度是什么？' },
  { icon: '🔍', category: '知识库', text: '入职需要准备哪些材料？' },
  { icon: '📊', category: '产品数据', text: '查一下本月库存不足的产品' },
  { icon: '📊', category: '产品数据', text: '各产品分类的库存分别是多少？' },
  { icon: '🖼️', category: '图片', text: '识别这张图片中的内容' },
  { icon: '🖥️', category: '服务器', text: '查询当前服务器的磁盘占用情况' },
]

interface Props {
  name: string
  /** 点击推荐问题卡片：直接以该问题发起一轮问答 */
  onAsk: (text: string) => void
}

export default function WelcomePanel({ name, onAsk }: Props) {
  return (
    <div
      className="chat-welcome"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        padding: '0 24px',
      }}
    >
      <Typography.Title level={4} style={{ margin: 0 }}>
        你好，{name}
      </Typography.Title>
      <Typography.Text type="secondary">
        可询问公司制度、流程等知识库问题，也可以查询产品库存、价格等数据
      </Typography.Text>
      <div className="chat-welcome-grid">
        {FOLLOWUPS.map((f) => (
          <button key={f.text} type="button" className="chat-followup-card" onClick={() => onAsk(f.text)}>
            <span className="chat-followup-icon" aria-hidden>
              {f.icon}
            </span>
            <span className="chat-followup-body">
              <span className="chat-followup-category">{f.category}</span>
              <span className="chat-followup-text">{f.text}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
