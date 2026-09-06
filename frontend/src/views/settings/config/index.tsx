import { App, Button, Card, Form, Input, Modal, Table, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { configApi, type ConfigItem } from '@/api/config'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

export default function ConfigList() {
  const { message } = App.useApp()
  const [list, setList] = useState<ConfigItem[]>([])
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<ConfigItem | null>(null)
  const [editValue, setEditValue] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [saving, setSaving] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      setList(await configApi.list())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  const openEdit = (record: ConfigItem) => {
    setEditing(record)
    setEditValue(record.config_value ?? '')
    setEditDesc(record.description ?? '')
  }

  const handleSave = async () => {
    if (!editing) return
    setSaving(true)
    try {
      await configApi.update(editing.id, { config_value: editValue, description: editDesc || undefined })
      message.success('保存成功')
      setEditing(null)
      loadList()
    } catch {
      // 已由拦截器提示
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '配置键', dataIndex: 'config_key', width: 180, render: (v: string) => <Typography.Text code>{v}</Typography.Text> },
    { title: '配置名称', dataIndex: 'config_name', width: 150 },
    {
      title: '配置值',
      dataIndex: 'config_value',
      ellipsis: true,
      render: (v: string | null) =>
        v ? <Typography.Text>{v}</Typography.Text> : <Typography.Text type="secondary">（空）</Typography.Text>,
    },
    { title: '说明', dataIndex: 'description', ellipsis: true, render: (v: string | null) => v || '-' },
    { title: '更新时间', dataIndex: 'updated_at', width: 150, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_: unknown, record: ConfigItem) => (
        <HasPermission code="config:update">
          <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
        </HasPermission>
      ),
    },
  ]

  return (
    <Card>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
        <Typography.Text type="secondary">
          系统全局配置项（品牌/文案等），由系统预置；图片类配置以 Data URL 存储。
        </Typography.Text>
        <Button icon={<ReloadOutlined />} onClick={loadList}>刷新</Button>
      </div>
      <Table rowKey="id" size="middle" columns={columns} dataSource={list} loading={loading} pagination={false} />

      {/* 编辑配置弹窗 */}
      <Modal
        title={`编辑配置：${editing?.config_name ?? ''}`}
        open={!!editing}
        onOk={handleSave}
        onCancel={() => setEditing(null)}
        confirmLoading={saving}
        width={520}
        destroyOnHidden
      >
        <Form layout="horizontal" labelCol={{ span: 5 }} wrapperCol={{ span: 17 }}>
          <Form.Item label="配置键">
            <Input value={editing?.config_key} disabled />
          </Form.Item>
          <Form.Item label="配置值">
            <Input.TextArea value={editValue} onChange={(e) => setEditValue(e.target.value)} rows={3} placeholder="配置值" />
          </Form.Item>
          <Form.Item label="说明">
            <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} maxLength={255} placeholder="配置说明" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
