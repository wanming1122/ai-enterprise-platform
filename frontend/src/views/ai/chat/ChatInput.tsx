/**
 * 输入区（AI 助手页）：placeholder 每 5 秒轮播引导、快捷提示标签（点击填入模板并聚焦）、
 * 图片上传预览与移除、TextArea 输入（回车发送/Shift+回车换行）、停止/发送按钮。
 * 纯展示组件，事件通过回调上抛给页面容器。
 */
import { useEffect, useRef, useState } from 'react'
import { Button, Input, Space, Tag, Typography, Upload } from 'antd'
import {
  DeleteOutlined,
  PictureOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons'

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

interface Props {
  input: string
  streaming: boolean
  currentConvId: number | null
  pendingImages: string[]
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
    <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
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
                  style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 6, border: '1px solid #e8e8e8' }}
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
            disabled={streaming}
            onPressEnter={(e) => {
              if (!e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
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
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {currentConvId ? `会话 #${currentConvId}` : '回车发送，Shift+回车换行'}
        </Typography.Text>
        {streaming ? (
          <Button danger icon={<StopOutlined />} onClick={onStop}>
            停止
          </Button>
        ) : (
          <Button type="primary" icon={<SendOutlined />} disabled={!input.trim()} onClick={onSend}>
            发送
          </Button>
        )}
      </div>
    </div>
  )
}
