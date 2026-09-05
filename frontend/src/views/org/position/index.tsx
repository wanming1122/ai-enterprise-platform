import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { positionApi, type PositionForm as PositionFormData, type PositionItem } from '@/api/position'

const STATUS_TEXT: Record<number, { text: string; color: string }> = {
  1: { text: '启用', color: 'green' },
  0: { text: '停用', color: 'red' },
}

export default function PositionManage() {
  const { message } = App.useApp()
  const [filterForm] = Form.useForm<{ keyword?: string; status?: number }>()
  const [form] = Form.useForm<PositionFormData>()
  const [filters, setFilters] = useState<{ keyword?: string; status?: number }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<PositionItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [roles, setRoles] = useState<{ id: number; name: string; code: string }[]>([])
  const [editing, setEditing] = useState<PositionItem | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await positionApi.list({ ...filters, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    positionApi.roleOptions().then(setRoles).catch(() => {
      // 提示已由拦截器统一处理
    })
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleSearch = (values: { keyword?: string; status?: number }) => {
    setFilters({ keyword: values.keyword || undefined, status: values.status })
    setPage(1)
  }

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (record: PositionItem) => {
    setEditing(record)
    form.setFieldsValue({
      name: record.name,
      code: record.code,
      level: record.level,
      base_salary: record.base_salary,
      role_id: record.role_id ?? undefined,
      description: record.description ?? undefined,
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      if (editing) {
        await positionApi.update(editing.id, values)
        message.success('编辑成功')
      } else {
        await positionApi.create(values)
        message.success('新增成功')
      }
      setModalOpen(false)
      loadList()
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (record: PositionItem) => {
    await positionApi.toggleStatus(record.id)
    message.success(record.status === 1 ? '已停用' : '已启用')
    loadList()
  }

  const handleRemove = async (record: PositionItem) => {
    await positionApi.remove(record.id)
    message.success('删除成功')
    loadList()
  }

  const columns = [
    { title: '职位名称', dataIndex: 'name', width: 130 },
    { title: '职位编码', dataIndex: 'code', width: 160 },
    { title: '职级', dataIndex: 'level', width: 70 },
    {
      title: '基本工资',
      dataIndex: 'base_salary',
      width: 120,
      render: (v: string) => `¥${Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`,
    },
    {
      title: '绑定角色',
      dataIndex: 'role_name',
      width: 130,
      render: (v: string | null) => (v ? <Tag color="blue">{v}</Tag> : <Typography.Text type="secondary">未绑定</Typography.Text>),
    },
    { title: '描述', dataIndex: 'description', ellipsis: true, render: (v: string) => v || '-' },
    { title: '在职人数', dataIndex: 'user_count', width: 90 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (s: number) => {
        const t = STATUS_TEXT[s] || { text: '未知', color: 'default' }
        return <Tag color={t.color}>{t.text}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 190,
      fixed: 'right' as const,
      render: (_: unknown, record: PositionItem) => (
        <Space size={4}>
          <HasPermission code="position:update">
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
            <Popconfirm title={record.status === 1 ? '确认停用该职位？' : '确认启用该职位？'} onConfirm={() => handleToggle(record)}>
              <Button type="link" size="small" danger={record.status === 1}>
                {record.status === 1 ? '停用' : '启用'}
              </Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="position:delete">
            <Popconfirm
              title="确认删除该职位？"
              description="删除后列表不再显示，数据保留。"
              onConfirm={() => handleRemove(record)}
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
          <Input.Search placeholder="职位名称/编码" allowClear style={{ width: 220 }} onSearch={(v) => handleSearch({ keyword: v })} />
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 110 }}>
            <Select.Option value={1}>启用</Select.Option>
            <Select.Option value={0}>停用</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
          </Space>
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }}>
        <HasPermission code="position:create">
          <Button type="primary" onClick={openCreate}>新增职位</Button>
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
        scroll={{ x: 1100 }}
      />

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editing ? '编辑职位' : '新增职位'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={520}
        forceRender
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="职位名称" rules={[{ required: true, message: '请输入职位名称' }]}>
            <Input placeholder="如：软件工程师" maxLength={64} />
          </Form.Item>
          <Form.Item
            name="code"
            label="职位编码"
            rules={[
              { required: true, message: '请输入职位编码' },
              { pattern: /^[A-Za-z][A-Za-z0-9_]*$/, message: '字母开头，仅含字母数字下划线' },
            ]}
          >
            <Input placeholder="如：software_engineer" maxLength={32} disabled={!!editing} />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="level" label="职级" initialValue={1} style={{ width: 140 }}>
              <InputNumber min={1} max={30} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="base_salary"
              label="月基本工资"
              rules={[{ required: true, message: '请输入基本工资' }]}
              style={{ width: 180 }}
            >
              <InputNumber min={0} precision={2} style={{ width: '100%' }} placeholder="0.00" addonAfter="¥" />
            </Form.Item>
          </Space>
          <Form.Item name="role_id" label="绑定角色（权限模板）">
            <Select allowClear placeholder="选择该职位用户默认获得的角色">
              {roles.map((r) => (
                <Select.Option key={r.id} value={r.id}>{r.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="description" label="职位描述">
            <Input.TextArea rows={3} placeholder="职位职责说明" maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
