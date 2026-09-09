/**
 * 长期记忆管理抽屉（AI 助手页头部入口）：
 * 查看 / 编辑 / 单条删除 / 清空本人记忆。数据来自 /ai/memories CRUD 接口。
 */
import { App, Button, Drawer, Empty, Input, List, Popconfirm, Tag, Typography } from 'antd'
import { DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { aiChatApi, type AIMemoryItem } from '@/api/aiChat'

interface Props {
  open: boolean
  onClose: () => void
}

export default function MemoryDrawer({ open, onClose }: Props) {
  const { message } = App.useApp()
  const [items, setItems] = useState<AIMemoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(
    async (p: number) => {
      setLoading(true)
      try {
        const res = await aiChatApi.memories({ page: p, page_size: 50 })
        setItems((prev) => (p === 1 ? res.list : [...prev, ...res.list]))
        setTotal(res.total)
        setPage(p)
      } catch {
        // 错误已由拦截器统一提示
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    if (open) load(1)
  }, [open, load])

  const handleDelete = async (id: number) => {
    try {
      await aiChatApi.deleteMemory(id)
      message.success('已删除')
      load(1)
    } catch {
      // 拦截器已提示
    }
  }

  const handleClear = async () => {
    try {
      await aiChatApi.clearMemories()
      message.success('已清空')
      load(1)
    } catch {
      // 拦截器已提示
    }
  }

  const handleSave = async (id: number) => {
    const text = draft.trim()
    if (!text) {
      message.warning('内容不能为空')
      return
    }
    setSaving(true)
    try {
      await aiChatApi.updateMemory(id, text)
      message.success('已保存')
      setEditingId(null)
      load(1)
    } catch {
      // 拦截器已提示
    } finally {
      setSaving(false)
    }
  }

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>长期记忆（{total}）</span>
          {total > 0 && (
            <Popconfirm title="确认清空全部记忆？" onConfirm={handleClear}>
              <Button size="small" danger>清空</Button>
            </Popconfirm>
          )}
        </div>
      }
      open={open}
      onClose={onClose}
      width={420}
    >
      <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
        这些是 AI 助手在历史对话中记住的关于你的信息，每次提问会召回相关内容。你可以编辑或删除。
      </Typography.Text>
      {items.length === 0 && !loading ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无记忆，对话中告知 AI 你的偏好即可积累" />
      ) : (
        <List
          loading={loading}
          dataSource={items}
          pagination={total > 50 ? { current: page, pageSize: 50, total, onChange: (p) => load(p), size: 'small' } : false}
          renderItem={(item) => (
            <List.Item
              actions={
                editingId === item.id
                  ? [
                      <Button key="save" size="small" type="primary" loading={saving} onClick={() => handleSave(item.id)}>
                        保存
                      </Button>,
                      <Button key="cancel" size="small" onClick={() => setEditingId(null)}>取消</Button>,
                    ]
                  : [
                      <Button
                        key="edit"
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => {
                          setEditingId(item.id)
                          setDraft(item.content)
                        }}
                      />,
                      <Popconfirm key="del" title="确认删除该条记忆？" onConfirm={() => handleDelete(item.id)}>
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>,
                    ]
              }
            >
              {editingId === item.id ? (
                <Input.TextArea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  autoSize={{ minRows: 2, maxRows: 6 }}
                  maxLength={300}
                />
              ) : (
                <div>
                  <Typography.Text style={{ fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {item.content}
                  </Typography.Text>
                  <div style={{ marginTop: 4 }}>
                    <Tag style={{ marginInlineEnd: 0 }} color={item.memory_type === 'preference' ? 'purple' : 'blue'}>
                      {item.memory_type === 'preference' ? '偏好' : '事实'}
                    </Tag>
                    <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                      {item.updated_at.slice(0, 19).replace('T', ' ')}
                    </Typography.Text>
                  </div>
                </div>
              )}
            </List.Item>
          )}
        />
      )}
    </Drawer>
  )
}


