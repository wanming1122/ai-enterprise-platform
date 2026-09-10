import { App, Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { CopyOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { INVITATION_STATUS_COLOR, invitationApi, type InvitationItem, type InvitationLogItem } from '@/api/invitation'
import { phoneRule } from '@/utils/phone'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

interface InvitationFormValues {
  name?: string
  phone?: string
  email?: string
  department_id: number
  role_id: number
  post?: string
  expires_days: number
  remark?: string
}

export default function InvitationList() {
  const { message, modal } = App.useApp()
  const [filterForm] = Form.useForm<{ keyword?: string; status?: number }>()
  const [form] = Form.useForm<InvitationFormValues>()
  const [filters, setFilters] = useState<{ keyword?: string; status?: number }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<InvitationItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [depts, setDepts] = useState<{ id: number; name: string }[]>([])
  const [roles, setRoles] = useState<{ id: number; name: string }[]>([])

  const [logsFor, setLogsFor] = useState<InvitationItem | null>(null)
  const [logs, setLogs] = useState<InvitationLogItem[]>([])

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await invitationApi.list({ ...filters, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    // 表单字典数据：部门树打平为下拉选项；角色取分页列表
    interface DeptNode { id: number; name: string; children?: DeptNode[] }
    import('@/api/department').then(({ deptApi }) => {
      deptApi.tree().then((tree) => {
        const flat: { id: number; name: string }[] = []
        const walk = (nodes: DeptNode[]) => {
          for (const n of nodes) {
            flat.push({ id: n.id, name: n.name })
            if (n.children?.length) walk(n.children)
          }
        }
        walk(tree as DeptNode[])
        setDepts(flat)
      })
    })
    import('@/api/role').then(({ roleApi }) => {
      roleApi.list({ page: 1, page_size: 100 }).then((res) => setRoles(res.list.map((r) => ({ id: r.id, name: r.name }))))
    })
  }, [])

  const openModal = () => {
    form.setFieldsValue({ name: undefined, phone: undefined, email: undefined, department_id: undefined, role_id: undefined, post: undefined, expires_days: 3, remark: undefined })
    setModalOpen(true)
  }

  const handleCreate = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      const inv = await invitationApi.create(values)
      setModalOpen(false)
      message.success('邀请已创建')
      loadList()
      copyLink(inv.invite_link ?? `/invite/${inv.token}`)
    } catch {
      // 已由拦截器提示
    } finally {
      setSaving(false)
    }
  }

  const copyLink = (link: string) => {
    const url = `${window.location.origin}${link}`
    navigator.clipboard
      ?.writeText(url)
      .then(() => message.success(`邀请链接已复制：${url}`))
      .catch(() => {
        modal.info({ title: '邀请链接', content: url })
      })
  }

  const openLogs = async (record: InvitationItem) => {
    setLogsFor(record)
    try {
      setLogs(await invitationApi.logs(record.id))
    } catch {
      // 已由拦截器提示，弹窗保持空列表
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '被邀请人', dataIndex: 'name', width: 100, render: (v: string | null) => v || '-' },
    { title: '预设部门', dataIndex: 'department_name', width: 110, render: (v: string | null) => v || '-' },
    { title: '预设角色', dataIndex: 'role_name', width: 110, render: (v: string | null) => v || '-' },
    { title: '预设岗位', dataIndex: 'post', width: 110, render: (v: string | null) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s: number, r: InvitationItem) => <Tag color={INVITATION_STATUS_COLOR[s]}>{r.status_label}</Tag>,
    },
    { title: '有效期至', dataIndex: 'expires_at', width: 140, render: fmtTime },
    { title: '创建时间', dataIndex: 'created_at', width: 140, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 260,
      fixed: 'right' as const,
      render: (_: unknown, record: InvitationItem) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => openLogs(record)}>日志</Button>
          <HasPermission code="invitation:create">
            <Tooltip title="复制邀请链接">
              <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => copyLink(record.invite_link ?? `/invite/${record.token}`)} />
            </Tooltip>
          </HasPermission>
          <HasPermission code="invitation:resend">
            <Popconfirm title="重发邀请？" description="将重新生成链接并顺延有效期。" onConfirm={() => { invitationApi.resend(record.id).then(() => { message.success('已重发'); loadList() }) }}>
              <Button type="link" size="small" disabled={![1, 2, 4].includes(record.status)}>重发</Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="invitation:revoke">
            <Popconfirm title="撤销邀请？" description="撤销后链接不可再注册。" onConfirm={() => { invitationApi.cancel(record.id).then(() => { message.success('已撤销'); loadList() }) }}>
              <Button type="link" size="small" disabled={![0, 1, 2, 4].includes(record.status)}>撤销</Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="invitation:delete">
            <Popconfirm
              title="删除邀请？"
              description="将同时删除其状态日志，不可恢复。"
              onConfirm={() => { invitationApi.remove(record.id).then(() => { message.success('已删除'); loadList() }) }}
            >
              <Button type="link" size="small" danger disabled={record.status === 3}>删除</Button>
            </Popconfirm>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={(v) => { setFilters({ keyword: v.keyword?.trim() || undefined, status: v.status }); setPage(1) }} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="keyword">
          <Input placeholder="被邀请人姓名" allowClear style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 110 }} options={[1, 2, 3, 4, 5].map((s) => ({ value: s, label: ['待发送', '已发送', '已打开', '已注册', '已过期', '已撤销'][s] }))} />
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
        <HasPermission code="invitation:create">
          <Button type="primary" icon={<PlusOutlined />} onClick={openModal}>新建邀请</Button>
        </HasPermission>
      </Space>

      <Table
        rowKey="id"
        size="middle"
        columns={columns}
        dataSource={list}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps) },
        }}
        scroll={{ x: 1200 }}
      />

      {/* 新建邀请弹窗 */}
      <Modal
        title="新建入职邀请"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={520}
        forceRender
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary">
          创建后生成专属邀请链接，外部人员通过链接注册后自动绑定预设部门与角色。
        </Typography.Paragraph>
        <Form form={form} layout="horizontal" labelCol={{ span: 5 }} wrapperCol={{ span: 17 }}>
          <Form.Item name="name" label="被邀请人">
            <Input placeholder="选填" maxLength={64} />
          </Form.Item>
          <Form.Item
            name="phone"
            label="手机号"
            rules={[
              { required: true, whitespace: true, message: '请输入手机号' },
              phoneRule(),
            ]}
          >
            <Input placeholder="请输入手机号" maxLength={20} />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="选填" maxLength={128} />
          </Form.Item>
          <Form.Item
            name="department_id"
            label="预设部门"
            rules={[{ required: true, message: '请选择预设部门' }]}
          >
            <Select
              placeholder="入职后归属部门"
              options={depts.map((d) => ({ value: d.id, label: d.name }))}
            />
          </Form.Item>
          <Form.Item
            name="role_id"
            label="预设角色"
            rules={[{ required: true, message: '请选择预设角色' }]}
          >
            <Select
              placeholder="入职后绑定角色"
              options={roles.map((r) => ({ value: r.id, label: r.name }))}
            />
          </Form.Item>
          <Form.Item name="post" label="预设岗位">
            <Input placeholder="选填" maxLength={64} />
          </Form.Item>
          <Form.Item name="expires_days" label="有效期" rules={[{ required: true, message: '请设置有效天数' }]}>
            <InputNumber min={1} max={30} precision={0} style={{ width: '100%' }} addonAfter="天" />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} placeholder="选填" maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 邀请日志抽屉 */}
      <Modal
        title={`邀请日志${logsFor ? `（${logsFor.name || '未填写'}）` : ''}`}
        open={!!logsFor}
        onCancel={() => setLogsFor(null)}
        footer={null}
        width={520}
      >
        {logs.map((l, i) => (
          <div key={l.id} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px dashed #f0f0f0' }}>
            <Tag color={i === logs.length - 1 ? 'processing' : 'default'} style={{ marginInlineEnd: 0 }}>{l.action}</Tag>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13 }}>{l.detail || '-'}</div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {fmtTime(l.created_at)} {l.ip ? `· ${l.ip}` : ''}
              </Typography.Text>
            </div>
          </div>
        ))}
        {!logs.length && <Typography.Text type="secondary">暂无日志</Typography.Text>}
      </Modal>
    </Card>
  )
}
