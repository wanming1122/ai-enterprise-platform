import './ThinkingIndicator.css'

/** 生成占位动画：三点跳动 + “正在思考…”。 */
export default function ThinkingIndicator({ text = '正在思考…' }: { text?: string }) {
  return (
    <div className="thinking-indicator">
      <span className="thinking-dots">
        <i />
        <i />
        <i />
      </span>
      <span className="thinking-text">{text}</span>
    </div>
  )
}
