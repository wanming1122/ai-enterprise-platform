import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Table,
  Tag,
} from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { PRODUCT_STATUS_OPTIONS, productApi, type ProductItem } from '@/api/product'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

interface ProductFormValues {
  name: string
  category?: string
  price?: number | null
  stock?: number | null
  description?: string
  status: number
}

export default function ProductManage() {
  const { message } = App.useApp()
  const [filterForm] = Form.useForm<{ keyword?: string; status?: number }>()
  const [form] = Form.useForm<ProductFormValues>()

  const [filters, setFilters] = useState<{ keyword?: string; status?: number }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<ProductItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ProductItem | null>(null)
  const [saving, setSaving] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await productApi.list({ ...filters, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleSearch = (values: { keyword?: string; status?: number }) => {
    setFilters({ keyword: values.keyword?.trim() || undefined, status: values.status })
    setPage(1)
  }

  const openModal = (record?: ProductItem) => {
    setEditing(record ?? null)
    if (record) {
      form.setFieldsValue({
        name: record.name,
        category: record.category ?? undefined,
        price: record.price ?? undefined,
        stock: record.stock ?? undefined,
        description: record.description ?? undefined,
        status: record.status === 0 ? 0 : 1,
      })
    } else {
      form.setFieldsValue({
        name: undefined, category: undefined, price: undefined,
        stock: undefined, description: undefined, status: 1,
      })
    }
    setModalOpen(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      const payload = {
        ...values,
        category: values.category || undefined,
        description: values.description || undefined,
        price: values.price ?? undefined,
        stock: values.stock ?? undefined,
      }
      if (editing) {
        await productApi.update(editing.id, payload)
        message.success('保存成功')
      } else {
        await productApi.create(payload)
        message.success('新增成功')
      }
      setModalOpen(false)
      loadList()
    } catch {
      // 校验/请求错误已由表单与拦截器提示
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', width: 160, render: (v: string) => <strong>{v}</strong> },
    { title: '分类', dataIndex: 'category', width: 110, render: (v: string | null) => v || '-' },
    {
      title: '价格',
      dataIndex: 'price',
      width: 110,
      render: (v: number | null) => (v != null ? `¥ ${v.toFixed(2)}` : '-'),
    },
    { title: '库存', dataIndex: 'stock', width: 90, render: (v: number | null) => v ?? '-' },
    { title: '描述', dataIndex: 'description', ellipsis: true, render: (v: string | null) => v || '-' },
    {
      title: '上架状态',
      dataIndex: 'status',
      width: 95,
      render: (s: number) => (
        <Tag color={s === 1 ? 'success' : 'default'}>{s === 1 ? '上架' : '下架'}</Tag>
      ),
    },
    { title: '创建时间', dataIndex: 'created_at', width: 140, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 130,
      fixed: 'right' as const,
      render: (_: unknown, record: ProductItem) => (
        <Space size={0}>
          <HasPermission code="product:update">
            <Button type="link" size="small" onClick={() => openModal(record)}>编辑</Button>
          </HasPermission>
          <HasPermission code="product:delete">
            <Popconfirm
              title="确认删除该产品？"
              description="删除后列表与 NL2SQL 查询均不再显示。"
              onConfirm={() => {
                productApi.remove(record.id).then(() => {
                  message.success('已删除')
                  loadList()
                })
              }}
            >
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={handleSearch} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="keyword">
          <Input placeholder="名称 / 分类 / 描述" allowClear style={{ width: 200 }} />
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 110 }} options={PRODUCT_STATUS_OPTIONS} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={loadList}>刷新</Button>
          </Space>
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }}>
        <HasPermission code="product:create">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>新增产品</Button>
        </HasPermission>
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={list}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
        scroll={{ x: 1000 }}
      />

      {/* 新增/编辑产品弹窗 */}
      <Modal
        title={editing ? '编辑产品' : '新增产品'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={520}
        forceRender
        destroyOnHidden
      >
        <Form form={form} layout="horizontal" labelCol={{ span: 5 }} wrapperCol={{ span: 17 }}>
          <Form.Item name="name" label="产品名称" rules={[{ required: true, message: '请输入产品名称' }, { max: 64, message: '不超过 64 字' }]}>
            <Input placeholder="产品名称" maxLength={64} />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ max: 32, message: '不超过 32 字' }]}>
            <Input placeholder="如：电子产品 / 办公用品" maxLength={32} />
          </Form.Item>
          <Form.Item name="price" label="价格">
            <InputNumber min={0} precision={2} style={{ width: '100%' }} placeholder="元" />
          </Form.Item>
          <Form.Item name="stock" label="库存">
            <InputNumber min={0} precision={0} style={{ width: '100%' }} placeholder="库存数量" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="产品描述（选填）" maxLength={255} />
          </Form.Item>
          <Form.Item name="status" label="上架状态">
            <Radio.Group>
              <Radio value={1}>上架</Radio>
              <Radio value={0}>下架</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
