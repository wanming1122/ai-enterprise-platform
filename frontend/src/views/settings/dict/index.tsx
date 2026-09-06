import { App, Button, Card, Drawer, Form, Input, InputNumber, Modal, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { dictApi, type DictItem, type DictTypeItem } from '@/api/dict'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

export default function DictList() {
  const { message } = App.useApp()
  const [typeForm] = Form.useForm<{ dict_name: string; dict_code?: string; description?: string }>()
  const [itemForm] = Form.useForm<{ item_label: string; item_value: string; sort_order?: number }>()

  const [types, setTypes] = useState<DictTypeItem[]>([])
  const [loading, setLoading] = useState(false)

  const [typeModalOpen, setTypeModalOpen] = useState(false)
  const [editingType, setEditingType] = useState<DictTypeItem | null>(null)
  const [saving, setSaving] = useState(false)

  const [itemsFor, setItemsFor] = useState<DictTypeItem | null>(null)
  const [items, setItems] = useState<DictItem[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)
  const [itemModalOpen, setItemModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<DictItem | null>(null)

  const loadTypes = useCallback(async () => {
    setLoading(true)
    try {
      setTypes(await dictApi.listTypes())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTypes()
  }, [loadTypes])

  const loadItems = useCallback(async (t: DictTypeItem) => {
    setItemsLoading(true)
    try {
      setItems(await dictApi.listItems(t.id))
    } finally {
      setItemsLoading(false)
    }
  }, [])

  const openTypeModal = (record?: DictTypeItem) => {
    setEditingType(record ?? null)
    typeForm.setFieldsValue(
      record
        ? { dict_name: record.dict_name, dict_code: record.dict_code, description: record.description ?? undefined }
        : { dict_name: undefined, dict_code: undefined, description: undefined },
    )
    setTypeModalOpen(true)
  }

  const handleTypeSave = async () => {
    const values = await typeForm.validateFields()
    setSaving(true)
    try {
      if (editingType) {
        await dictApi.updateType(editingType.id, { dict_name: values.dict_name, description: values.description })
        message.success('保存成功')
      } else {
        await dictApi.createType({ dict_name: values.dict_name, dict_code: values.dict_code!, description: values.description })
        message.success('新增成功')
      }
      setTypeModalOpen(false)
      loadTypes()
    } catch {
      // 已由拦截器提示
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteType = async (record: DictTypeItem) => {
    await dictApi.removeType(record.id)
    message.success('已删除（字典项一并停用）')
    if (itemsFor?.id === record.id) setItemsFor(null)
    loadTypes()
  }

  const openItems = (record: DictTypeItem) => {
    setItemsFor(record)
    loadItems(record)
  }

  const openItemModal = (record?: DictItem) => {
    setEditingItem(record ?? null)
    itemForm.setFieldsValue(
      record
        ? { item_label: record.item_label, item_value: record.item_value, sort_order: record.sort_order }
        : { item_label: undefined, item_value: undefined, sort_order: 0 },
    )
    setItemModalOpen(true)
  }

  const handleItemSave = async () => {
    if (!itemsFor) return
    const values = await itemForm.validateFields()
    setSaving(true)
    try {
      if (editingItem) {
        await dictApi.updateItem(editingItem.id, values)
        message.success('保存成功')
      } else {
        await dictApi.createItem(itemsFor.id, values)
        message.success('新增成功')
      }
      setItemModalOpen(false)
      loadItems(itemsFor)
      loadTypes()
    } catch {
      // 已由拦截器提示
    } finally {
      setSaving(false)
    }
  }

  const typeColumns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '字典名称', dataIndex: 'dict_name', width: 150 },
    { title: '字典编码', dataIndex: 'dict_code', width: 160, render: (v: string) => <Tag>{v}</Tag> },
    { title: '说明', dataIndex: 'description', ellipsis: true, render: (v: string | null) => v || '-' },
    { title: '字典项数', dataIndex: 'item_count', width: 90 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 85,
      render: (s: number) => <Tag color={s === 1 ? 'success' : 'default'}>{s === 1 ? '启用' : '停用'}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', width: 140, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: DictTypeItem) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => openItems(record)}>字典项</Button>
          <HasPermission code="dict:update">
            <Button type="link" size="small" onClick={() => openTypeModal(record)}>编辑</Button>
          </HasPermission>
          <HasPermission code="dict:delete">
            <Popconfirm
              title="确认删除该字典类型？"
              description="其下字典项将一并停用。"
              onConfirm={() => handleDeleteType(record)}
            >
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          </HasPermission>
        </Space>
      ),
    },
  ]

  const itemColumns = [
    { title: '标签', dataIndex: 'item_label', width: 130 },
    { title: '值', dataIndex: 'item_value', width: 130, render: (v: string) => <Tag>{v}</Tag> },
    { title: '排序', dataIndex: 'sort_order', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 85,
      render: (s: number) => <Tag color={s === 1 ? 'success' : 'default'}>{s === 1 ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 130,
      render: (_: unknown, record: DictItem) => (
        <Space size={0}>
          <HasPermission code="dict:update">
            <Button type="link" size="small" onClick={() => openItemModal(record)}>编辑</Button>
            {record.status === 0 && (
              <Button type="link" size="small" onClick={async () => { await dictApi.updateItem(record.id, { status: 1 }); loadItems(itemsFor!) }}>
                启用
              </Button>
            )}
          </HasPermission>
          <HasPermission code="dict:delete">
            <Popconfirm title="确认删除该字典项？" onConfirm={async () => { await dictApi.removeItem(record.id); loadItems(itemsFor!); loadTypes() }}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
        <Typography.Text type="secondary">
          基础字典数据两级维护：字典类型 → 字典项；删除类型会级联停用其字典项。
        </Typography.Text>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadTypes}>刷新</Button>
          <HasPermission code="dict:create">
            <Button type="primary" icon={<PlusOutlined />} onClick={() => openTypeModal()}>新增字典</Button>
          </HasPermission>
        </Space>
      </div>

      <Table rowKey="id" size="middle" columns={typeColumns} dataSource={types} loading={loading} pagination={false} />

      {/* 新增/编辑字典类型 */}
      <Modal
        title={editingType ? '编辑字典类型' : '新增字典类型'}
        open={typeModalOpen}
        onOk={handleTypeSave}
        onCancel={() => setTypeModalOpen(false)}
        confirmLoading={saving}
        width={480}
        forceRender
        destroyOnHidden
      >
        <Form form={typeForm} layout="horizontal" labelCol={{ span: 5 }} wrapperCol={{ span: 17 }}>
          <Form.Item name="dict_name" label="字典名称" rules={[{ required: true, message: '请输入字典名称' }]}>
            <Input placeholder="如：用户性别" maxLength={64} />
          </Form.Item>
          <Form.Item
            name="dict_code"
            label="字典编码"
            rules={[
              { required: !editingType, message: '请输入字典编码' },
              { pattern: /^[a-z][a-z0-9_]*$/, message: '小写字母开头，仅含小写字母/数字/下划线' },
            ]}
          >
            <Input placeholder="如：gender" maxLength={64} disabled={!!editingType} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input placeholder="选填" maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 字典项抽屉 */}
      <Drawer
        title={`字典项${itemsFor ? `：${itemsFor.dict_name}（${itemsFor.dict_code}）` : ''}`}
        width={640}
        open={!!itemsFor}
        onClose={() => setItemsFor(null)}
        destroyOnHidden
      >
        <div style={{ marginBottom: 12 }}>
          <HasPermission code="dict:update">
            <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => openItemModal()}>
              新增字典项
            </Button>
          </HasPermission>
        </div>
        <Table
          rowKey="id"
          size="small"
          columns={itemColumns}
          dataSource={items}
          loading={itemsLoading}
          pagination={false}
        />
      </Drawer>

      {/* 新增/编辑字典项 */}
      <Modal
        title={editingItem ? '编辑字典项' : '新增字典项'}
        open={itemModalOpen}
        onOk={handleItemSave}
        onCancel={() => setItemModalOpen(false)}
        confirmLoading={saving}
        width={460}
        forceRender
        destroyOnHidden
      >
        <Form form={itemForm} layout="horizontal" labelCol={{ span: 5 }} wrapperCol={{ span: 17 }}>
          <Form.Item name="item_label" label="标签" rules={[{ required: true, message: '请输入标签' }]}>
            <Input placeholder="如：男" maxLength={64} />
          </Form.Item>
          <Form.Item name="item_value" label="值" rules={[{ required: true, message: '请输入值' }]}>
            <Input placeholder="如：1" maxLength={64} />
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <InputNumber min={0} precision={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
