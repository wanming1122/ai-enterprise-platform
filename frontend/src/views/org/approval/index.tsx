import { App, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { approvalApi, type ApprovalItem } from '@/api/approval'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

const STATUS_OPTIONS = [
  { value: 0, label: '待审批' },
  { value: 1, label: '通过' },
  { value: 2, label: '驳回' },
]
const STATUS_COLOR: Record<number, string> = { 0: 'warning', 1: 'success', 2: 'error' }
const { CheckableTag } = Tag

export default function ApprovalList() {
  const { message } = App.useApp()
  const [filterForm] = Form.useForm<{ keyword?: string; status?: number }>()
  const [filters, setFilters] = useState<{ keyword?: string; status?: number }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<ApprovalItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [rejecting, setRejecting] = useState<ApprovalItem | null>(null)
  const [rejectComment, setRejectComment] = useState('')
  const [saving, setSaving] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await approvalApi.list({ ...filters, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleApprove = async (record: ApprovalItem) => {
    await approvalApi.approve(record.id)
    message.success(`已通过 ${record.username} 的注册申请`)
    loadList()
  }

  const handleReject = async () => {
    if (!rejecting) return
    setSaving(true)
    try {
      await approvalApi.reject(rejecting.id, rejectComment.trim() || undefined)
      message.success('已驳回')
      setRejecting(null)
      loadList()
    } catch {
      // 已由拦截器提示
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '申请账号', dataIndex: 'username', width: 130 },
    { title: '姓名', dataIndex: 'real_name', width: 100, render: (v: string | null) => v || '-' },
    { title: '申请角色', dataIndex: 'apply_role_name', width: 110, render: (v: string | null) => v || '-' },
    { title: '手机号', dataIndex: 'phone', width: 120, render: (v: string | null) => v || '-' },
    {
      title: '申请说明',
      dataIndex: 'apply_comment',
      ellipsis: true,
      render: (v: string | null) => (v ? <Tooltip title={v}>{v}</Tooltip> : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s: number, r: ApprovalItem) => <Tag color={STATUS_COLOR[s]}>{r.status_label}</Tag>,
    },
    { title: '审批人', dataIndex: 'reviewer', width: 100, render: (v: string | null) => v || '-' },
    { title: '审批时间', dataIndex: 'reviewed_at', width: 140, render: fmtTime },
    { title: '申请时间', dataIndex: 'created_at', width: 140, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right' as const,
      render: (_: unknown, record: ApprovalItem) => (
        <Space size={0}>
          <HasPermission code="approval:approve">
            <Popconfirm
              title={`通过 ${record.username} 的注册申请？`}
              description="通过后将激活账号并绑定其申请角色。"
              onConfirm={() => handleApprove(record)}
            >
              <Button type="link" size="small" disabled={record.status !== 0}>通过</Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="approval:reject">
            <Button
              type="link"
              size="small"
              danger
              disabled={record.status !== 0}
              onClick={() => {
                setRejecting(record)
                setRejectComment('')
              }}
            >
              驳回
            </Button>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={(v) => { setFilters({ keyword: v.keyword?.trim() || undefined, status: v.status }); setPage(1) }} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="keyword">
          <Input placeholder="账号 / 姓名" allowClear style={{ width: 180 }} />
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 110 }} options={STATUS_OPTIONS} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={loadList}>刷新</Button>
          </Space>
        </Form.Item>
      </Form>

      <div style={{ marginBottom: 12 }}>
        <Space size={6} align="center">
          <Typography.Text type="secondary">状态快筛：</Typography.Text>
          <CheckableTag checked={filters.status === undefined} onChange={() => { setFilters({}); setPage(1) }}>全部</CheckableTag>
          {STATUS_OPTIONS.map((o) => (
            <CheckableTag
              key={o.value}
              checked={filters.status === o.value}
              onChange={() => { setFilters({ status: o.value }); setPage(1) }}
            >
              {o.label}
            </CheckableTag>
          ))}
        </Space>
      </div>

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
        scroll={{ x: 1300 }}
      />

      {/* 驳回弹窗（意见可选） */}
      <Modal
        title={`驳回 ${rejecting?.username ?? ''} 的注册申请`}
        open={!!rejecting}
        onOk={handleReject}
        onCancel={() => setRejecting(null)}
        confirmLoading={saving}
        okText="确认驳回"
        okButtonProps={{ danger: true }}
        width={460}
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary">
          驳回后该申请关闭，账号保持停用不可登录。
        </Typography.Paragraph>
        <Input.TextArea
          value={rejectComment}
          onChange={(e) => setRejectComment(e.target.value)}
          placeholder="驳回意见（可选）"
          rows={3}
          maxLength={255}
        />
      </Modal>
    </Card>
  )
}
