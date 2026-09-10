/**
 * 输入区（AI 助手页）：placeholder 每 5 秒轮播引导、快捷提示标签（点击填入模板并聚焦）、
 * 图片上传预览与移除、TextArea 输入（回车发送/Shift+回车换行；流式生成中回车=停止，输入框不禁用可继续打字）、
 * 上下文容量圆环（悬停浮层：总量/进度条/分类明细/缓存命中率）、模型切换下拉、深度思考开关、停止/发送按钮。
 * 纯展示组件，事件通过回调上抛给页面容器。
 */
import { useEffect, useRef, useState } from 'react'
import { Button, Dropdown, Input, Popover, Progress, Space, Switch, Tag, Typography, Upload } from 'antd'
import {
  DeleteOutlined,
  DownOutlined,
  PictureOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons'
import type { AIModelOption, ContextUsage } from '@/api/aiChat'

/** placeholder 轮播文案 */
const PLACEHOLDERS = [
  '可以询问制度、流程等知识库问题；涉及产品数据会自动查询 product 表；可附图片提问',
  '试试：公司的年假制度是什么？',
  '试试：查一下本月库存不足的产品',
  '试试：识别上传图片中的内容',
  '试试：查询当前服务器的磁盘占用情况',
]

/** 快捷提示：点击自动填入对应前缀模板，供继续编辑 */
const QUICK_PROMPTS = [
  { label: '问知识库', text: '帮我查一下公司制度里关于…' },
  { label: '查产品数据', text: '查一下产品的…' },
  { label: '服务器状态', text: '查询服务器…' },
]

/** 分类明细固定配色（圆点），按 tokens 降序依次取色 */
const BREAKDOWN_COLORS = ['#1677ff', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#fa8c16']

/** 大数缩写：12345 → 1.2万 */
const fmtTokens = (n: number) => (n >= 10000 ? `${(n / 10000).toFixed(1)}万` : n.toLocaleString())

/** 百分比格式化：≥10% 取整；≥0.1% 保留 1 位小数；<0.1% 显示 "<0.1%"（大窗口下避免恒显 0%） */
const fmtPct = (pct: number) => {
  if (pct >= 10) return `${Math.round(pct)}%`
  if (pct >= 0.1) return `${pct.toFixed(1)}%`
  return pct > 0 ? '<0.1%' : '0%'
}

/** 上下文容量圆环：底环 + 按百分比描边的前景弧线 */
function ContextRing({ percent }: { percent: number }) {
  const r = 9
  const c = 2 * Math.PI * r
  return (
    <svg width={24} height={24} viewBox="0 0 24 24" style={{ display: 'block' }}>
      <circle cx={12} cy={12} r={r} fill="none" stroke="var(--ant-color-fill-secondary)" strokeWidth={3} />
      <circle
        cx={12}
        cy={12}
        r={r}
        fill="none"
        stroke="var(--ant-color-primary)"
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - Math.min(100, Math.max(0, percent)) / 100)}
        transform="rotate(-90 12 12)"
        style={{ transition: 'stroke-dashoffset 0.3s' }}
      />
    </svg>
  )
}

/** 上下文容量浮层：圆环悬停触发，展示总量、进度条、分类明细与缓存命中率 */
function ContextPopover({ contextUsage }: { contextUsage: ContextUsage }) {
  const { used, total, breakdown, cacheHitRate } = contextUsage
  const percent = Math.min(100, total > 0 ? (used / total) * 100 : 0)
  // 过滤 0 值分项（如本轮无工具结果），避免出现 "工具结果 0" 这类空行
  const sorted = [...breakdown].filter((b) => b.tokens > 0).sort((a, b) => b.tokens - a.tokens)
  return (
    <Popover
      trigger="hover"
      placement="topLeft"
      content={
        <div style={{ width: 300 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <Typography.Text strong style={{ fontSize: 13 }}>
              上下文容量
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {fmtTokens(used)}/{fmtTokens(total)}（{fmtPct(percent)}）
            </Typography.Text>
          </div>
          <Progress percent={percent} size="small" showInfo={false} style={{ marginBottom: 8 }} />
          {sorted.map((item, i) => (
            <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
              <Space size={6}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 4,
                    background: BREAKDOWN_COLORS[i % BREAKDOWN_COLORS.length],
                    display: 'inline-block',
                  }}
                />
                <Typography.Text style={{ fontSize: 12 }}>{item.label}</Typography.Text>
              </Space>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {fmtTokens(item.tokens)} · {fmtPct(total > 0 ? (item.tokens / total) * 100 : 0)}
              </Typography.Text>
            </div>
          ))}
          {cacheHitRate != null && (
            <>
              <div style={{ borderTop: '1px solid var(--ant-color-split)', margin: '6px 0' }} />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                缓存命中率 {(cacheHitRate * 100).toFixed(1)}%
              </Typography.Text>
            </>
          )}
        </div>
      }
    >
      <span style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <ContextRing percent={percent} />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {fmtPct(percent)}
        </Typography.Text>
      </span>
    </Popover>
  )
}

interface Props {
  input: string
  streaming: boolean
  currentConvId: number | null
  pendingImages: string[]
  /** 深度思考开关（展示在发送按钮左侧，状态由容器/useChat 持有） */
  deepThinking: boolean
  onDeepThinkingChange: (v: boolean) => void
  /** 上下文容量明细（最近一轮统计，圆环悬停浮层展示） */
  contextUsage?: ContextUsage | null
  /** 启用中的生成模型与当前选择（模型切换下拉） */
  models?: AIModelOption[]
  currentModelId?: number | null
  onModelChange?: (id: number) => void
  onInputChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  onPickImage: (file: File) => Promise<boolean> | boolean
  onRemoveImage: (index: number) => void
}

export default function ChatInput({
  input,
  streaming,
  currentConvId,
  pendingImages,
  deepThinking,
  onDeepThinkingChange,
  contextUsage,
  models = [],
  currentModelId = null,
  onModelChange,
  onInputChange,
  onSend,
  onStop,
  onPickImage,
  onRemoveImage,
}: Props) {
  const [phIdx, setPhIdx] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // placeholder 轮播（每 5s 切换一条引导）
  useEffect(() => {
    const timer = window.setInterval(() => setPhIdx((i) => (i + 1) % PLACEHOLDERS.length), 5000)
    return () => window.clearInterval(timer)
  }, [])

  /** 快捷提示：填入模板并聚焦输入框等待补充 */
  const fillPrompt = (text: string) => {
    if (streaming) return
    onInputChange(text)
    textareaRef.current?.focus()
  }

  return (
    <div style={{ borderTop: '1px solid var(--ant-color-split)', paddingTop: 8 }}>
      {/* 快捷提示标签 */}
      <Space size={6} wrap style={{ marginBottom: 6 }}>
        {QUICK_PROMPTS.map((p) => (
          <Tag
            key={p.label}
            style={{ cursor: streaming ? 'not-allowed' : 'pointer', marginInlineEnd: 0 }}
            onClick={() => fillPrompt(p.text)}
          >
            {p.label}
          </Tag>
        ))}
      </Space>

      {pendingImages.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <Space size={8} wrap>
            {pendingImages.map((url, i) => (
              <div key={i} style={{ position: 'relative', lineHeight: 0 }}>
                <img
                  src={url}
                  alt={`附图${i + 1}`}
                  style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 6, border: '1px solid var(--ant-color-border-secondary)' }}
                />
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  style={{ position: 'absolute', top: -8, right: -8, minWidth: 20, height: 20, padding: 0 }}
                  onClick={() => onRemoveImage(i)}
                />
              </div>
            ))}
          </Space>
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <Upload
          accept="image/png,image/jpeg,image/webp"
          showUploadList={false}
          beforeUpload={onPickImage}
          disabled={streaming || pendingImages.length >= 3}
        >
          <Button
            icon={<PictureOutlined />}
            disabled={streaming || pendingImages.length >= 3}
            title="附带图片（最多3张，自动压缩）"
          />
        </Upload>
        <div style={{ flex: 1 }}>
          <Input.TextArea
            ref={textareaRef}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            placeholder={PLACEHOLDERS[phIdx % PLACEHOLDERS.length]}
            autoSize={{ minRows: 2, maxRows: 5 }}
            maxLength={2000}
            onPressEnter={(e) => {
              if (e.shiftKey || e.nativeEvent.isComposing) return
              e.preventDefault()
              // 流式生成中再次回车 = 停止生成（对齐主流聊天产品交互）
              if (streaming) {
                onStop()
              } else {
                onSend()
              }
            }}
          />
        </div>
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: 8,
        }}
      >
        <Space size={10} align="center">
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {currentConvId ? `会话 #${currentConvId}` : '回车发送，Shift+回车换行'}
          </Typography.Text>
        </Space>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* 上下文容量圆环：悬停显示分类明细浮层，置于模型切换左侧 */}
          {contextUsage && contextUsage.total > 0 && (
            <ContextPopover contextUsage={contextUsage} />
          )}
          {/* 模型切换下拉：列出启用中的生成模型，选择持久化到用户偏好 */}
          {models.length > 0 && (
            <Dropdown
              menu={{
                items: models.map((m) => ({
                  key: String(m.id),
                  label: `${m.model_name}${m.is_default ? '（默认）' : ''}`,
                })),
                onClick: ({ key }) => onModelChange?.(Number(key)),
                selectable: true,
                selectedKeys: currentModelId ? [String(currentModelId)] : [],
              }}
            >
              <Button type="text" size="small" title="切换生成模型">
                {models.find((m) => m.id === currentModelId)?.model_name ??
                  models.find((m) => m.is_default)?.model_name ??
                  '默认模型'}{' '}
                <DownOutlined style={{ fontSize: 10 }} />
              </Button>
            </Dropdown>
          )}
          {/* 深度思考开关：置于发送/停止按钮左侧，流式中禁用 */}
          <Space size={6}>
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              深度思考
            </Typography.Text>
            <Switch
              size="small"
              checked={deepThinking}
              checkedChildren="开"
              unCheckedChildren="关"
              onChange={onDeepThinkingChange}
              disabled={streaming}
            />
          </Space>
          {streaming ? (
            <Button danger icon={<StopOutlined />} onClick={onStop}>
              停止
            </Button>
          ) : (
            <Button type="primary" icon={<SendOutlined />} disabled={!input.trim()} onClick={() => onSend()}>
              发送
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
