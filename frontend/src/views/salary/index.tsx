import {
  App,
  Button,
  Card,
  DatePicker,
  Descriptions,
  Drawer,
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
  TreeSelect,
  Typography,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { salaryApi, type SalaryDetail, type SalaryItem } from '@/api/salary'
import { userApi, type DeptOption } from '@/api/user'

interface UserOption {
  id: number
  username: string
  real_name: string | null
}

/** 部门树 → TreeSelect treeData */
function toTreeData(depts: DeptOption[]): { value: number; title: string; children?: unknown[] }[] {
  return depts.map((d) => ({
    value: d.id,
    title: d.name,
    children: d.children?.length ? (toTreeData(d.children) as unknown[]) : undefined,
  }))
}

const STATUS_TAG: Record<number, { text: string; color: string }> = {
  0: { text: '草稿', color: 'orange' },
  1: { text: '已确认', color: 'blue' },
  2: { text: '已发放', color: 'green' },
}

const money = (v: string | null | undefined) =>
  v == null ? '-' : `¥${Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`

export default function SalaryManage() {
  const { message, modal } = App.useApp()
  const [filterForm] = Form.useForm<{
    year_month?: Dayjs
    department_id?: number
    user_id?: number
    status?: number
  }>()
  const [generateForm] = Form.useForm<{ year_month: Dayjs }>()
  const [adjustForm] = Form.useForm<{
    user_id: number
    adjust_type: number
    amount: number
    reason: string
    year_month?: Dayjs
  }>()
  const [filters, setFilters] = useState<{
    year_month?: string
    department_id?: number
    user_id?: number
    status?: number
  }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<SalaryItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [depts, setDepts] = useState<DeptOption[]>([])
  const [users, setUsers] = useState<UserOption[]>([])
  const [generateOpen, setGenerateOpen] = useState(false)
  const [generateing, setGenerateing] = useState(false)
  const [adjustOpen, setAdjustOpen] = useState(false)
  const [adjustSaving, setAdjustSaving] = useState(false)
  const [detail, setDetail] = useState<SalaryDetail | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const loadOptions = useCallback(async () => {
    try {
      const [d, u] = await Promise.all([userApi.departments(), userApi.users()])
      setDepts(d)
      setUsers(u)
    } catch {
      // 提示已由拦截器统一处理
    }
  }, [])

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await salaryApi.list({ ...filters, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    loadOptions()
  }, [loadOptions])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleSearch = (values: {
    year_month?: Dayjs
    department_id?: number
    user_id?: number
    status?: number
  }) => {
    setFilters({
      year_month: values.year_month ? values.year_month.format('YYYY-MM') : undefined,
      department_id: values.department_id,
      user_id: values.user_id,
      status: values.status,
    })
    setPage(1)
  }

  const openGenerate = () => {
    setGenerateOpen(true)
  }

  const handleGenerate = async () => {
    const values = await generateForm.validateFields()
    setGenerateing(true)
    try {
      const res = await salaryApi.generate({ year_month: values.year_month.format('YYYY-MM') })
      const tips = [`生成/重算 ${res.generated} 条`]
      if (res.locked) tips.push(`${res.locked} 条已锁定跳过`)
      if (res.no_position.length) tips.push(`${res.no_position.length} 人无职位跳过`)
      modal.success({ title: `工资单处理完成（${res.year_month}）`, content: tips.join('，') })
      setGenerateOpen(false)
      setFilters({ year_month: res.year_month })
      filterForm.setFieldsValue({ year_month: values.year_month })
      setPage(1)
    } finally {
      setGenerateing(false)
    }
  }

  const handleAdjust = async () => {
    const values = await adjustForm.validateFields()
    setAdjustSaving(true)
    try {
      await salaryApi.createAdjustment({
        user_id: values.user_id,
        adjust_type: values.adjust_type,
        amount: values.amount,
        reason: values.reason,
        year_month: values.year_month ? values.year_month.format('YYYY-MM') : undefined,
      })
      message.success('奖惩录入成功，重新生成工资单后生效')
      setAdjustOpen(false)
      adjustForm.resetFields()
    } finally {
      setAdjustSaving(false)
    }
  }

  const handleConfirm = async (record: SalaryItem) => {
    await salaryApi.confirm(record.id)
    message.success('已确认，工资单锁定')
    loadList()
  }

  const handlePay = async (record: SalaryItem) => {
    await salaryApi.pay(record.id)
    message.success('已发放')
    loadList()
  }

  const openDetail = async (record: SalaryItem) => {
    const res = await salaryApi.detail(record.id)
    setDetail(res)
    setDetailOpen(true)
  }

  const columns = [
    { title: '姓名', dataIndex: 'real_name', width: 90, render: (v: string | null) => v || '-' },
    { title: '账号', dataIndex: 'username', width: 110 },
    { title: '部门', dataIndex: 'dept_name', width: 95, render: (v: string | null) => v || '-' },
    { title: '月份', dataIndex: 'year_month', width: 85 },
    { title: '职位', dataIndex: 'position_name', width: 110 },
    { title: '基本工资', dataIndex: 'base_salary', width: 105, render: money },
    {
      title: '考勤增减',
      dataIndex: 'attendance_adjust',
      width: 105,
      render: (v: string) => (
        <span style={{ color: Number(v) < 0 ? '#cf1322' : Number(v) > 0 ? '#3f8600' : undefined }}>{money(v)}</span>
      ),
    },
    {
      title: '手动奖惩',
      dataIndex: 'manual_adjust',
      width: 105,
      render: (v: string) => (
        <span style={{ color: Number(v) < 0 ? '#cf1322' : Number(v) > 0 ? '#3f8600' : undefined }}>{money(v)}</span>
      ),
    },
    { title: '应发合计', dataIndex: 'total_salary', width: 115, render: money },
    {
      title: '状态',
      dataIndex: 'status',
      width: 85,
      render: (s: number) => {
        const t = STATUS_TAG[s] || { text: '未知', color: 'default' }
        return <Tag color={t.color}>{t.text}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      fixed: 'right' as const,
      render: (_: unknown, record: SalaryItem) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => openDetail(record)}>明细</Button>
          {record.status === 0 && (
            <HasPermission code="salary:confirm">
              <Popconfirm
                title={`确认 ${record.year_month} 工资单？`}
                description="确认后将锁定，不可再重算。"
                onConfirm={() => handleConfirm(record)}
              >
                <Button type="link" size="small">确认</Button>
              </Popconfirm>
            </HasPermission>
          )}
          {record.status === 1 && (
            <HasPermission code="salary:pay">
              <Popconfirm
                title={`发放 ${record.year_month} 工资单？`}
                description="发放后即视为工资已到账。"
                onConfirm={() => handlePay(record)}
              >
                <Button type="link" size="small" danger>发放</Button>
              </Popconfirm>
            </HasPermission>
          )}
        </Space>
      ),
    },
  ]

  const adjustTypeText = (t: number) => (t === 1 ? '奖励' : '罚款')

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={handleSearch} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="year_month">
          <DatePicker picker="month" placeholder="选择月份" style={{ width: 130 }} />
        </Form.Item>
        <Form.Item name="department_id">
          <TreeSelect placeholder="选择部门" allowClear treeData={toTreeData(depts) as never} style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="user_id">
          <Select placeholder="选择员工" allowClear showSearch optionFilterProp="label" style={{ width: 150 }}>
            {users.map((u) => (
              <Select.Option key={u.id} value={u.id} label={u.username}>
                {u.real_name ? `${u.real_name}（${u.username}）` : u.username}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 110 }}>
            <Select.Option value={0}>草稿</Select.Option>
            <Select.Option value={1}>已确认</Select.Option>
            <Select.Option value={2}>已发放</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
          </Space>
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }} wrap>
        <HasPermission code="salary:generate">
          <Button type="primary" onClick={openGenerate}>生成/重算工资单</Button>
        </HasPermission>
        <HasPermission code="salary:adjust">
          <Button onClick={() => { adjustForm.resetFields(); setAdjustOpen(true) }}>奖惩录入</Button>
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
        scroll={{ x: 1150 }}
      />

      {/* 生成/重算弹窗 */}
      <Modal
        title="生成/重算工资单"
        open={generateOpen}
        onOk={handleGenerate}
        onCancel={() => setGenerateOpen(false)}
        confirmLoading={generateing}
        width={420}
      >
        <Form form={generateForm} layout="vertical">
          <Form.Item name="year_month" label="工资月份" rules={[{ required: true, message: '请选择月份' }]}>
            <DatePicker picker="month" style={{ width: '100%' }} placeholder="选择月份" />
          </Form.Item>
          <Typography.Text type="secondary">
            基本工资取员工当前职位；考勤增减按考勤规则逐条计算；奖惩取归属当月的手动奖惩。
            已确认/已发放的工资单不会重算。
          </Typography.Text>
        </Form>
      </Modal>

      {/* 奖惩录入弹窗 */}
      <Modal
        title="奖惩录入"
        open={adjustOpen}
        onOk={handleAdjust}
        onCancel={() => setAdjustOpen(false)}
        confirmLoading={adjustSaving}
        width={480}
        forceRender
      >
        <Form form={adjustForm} layout="vertical" initialValues={{ adjust_type: 1 }}>
          <Form.Item name="user_id" label="员工" rules={[{ required: true, message: '请选择员工' }]}>
            <Select placeholder="选择员工" showSearch optionFilterProp="label">
              {users.map((u) => (
                <Select.Option key={u.id} value={u.id} label={u.username}>
                  {u.real_name ? `${u.real_name}（${u.username}）` : u.username}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="adjust_type" label="类型" style={{ width: 160 }}>
              <Radio.Group>
                <Radio value={1}>奖励</Radio>
                <Radio value={2}>罚款</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]} style={{ width: 180 }}>
              <InputNumber min={0.01} precision={2} style={{ width: '100%' }} addonAfter="¥" />
            </Form.Item>
          </Space>
          <Form.Item name="reason" label="事由" rules={[{ required: true, message: '请输入事由' }]}>
            <Input.TextArea rows={2} placeholder="如：项目攻坚奖励" maxLength={255} />
          </Form.Item>
          <Form.Item name="year_month" label="归属月份（不填则录入后需手动指定月份生成时计入）">
            <DatePicker picker="month" style={{ width: '100%' }} placeholder="选择归属月份" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 明细抽屉 */}
      <Drawer
        title="工资单明细"
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={640}
      >
        {detail && (
          <>
            <Descriptions
              size="small"
              column={2}
              bordered
              items={[
                { key: 'name', label: '员工', children: `${detail.payroll.real_name || '-'}（${detail.payroll.username}）` },
                { key: 'month', label: '月份', children: detail.payroll.year_month },
                { key: 'pos', label: '职位', children: detail.payroll.position_name },
                { key: 'status', label: '状态', children: detail.payroll.status_label },
                { key: 'base', label: '① 基本工资', children: money(detail.payroll.base_salary) },
                { key: 'att', label: '② 考勤增减', children: money(detail.payroll.attendance_adjust) },
                { key: 'manual', label: '③ 手动奖惩', children: money(detail.payroll.manual_adjust) },
                { key: 'total', label: '应发合计', children: <b>{money(detail.payroll.total_salary)}</b> },
              ]}
            />
            <Typography.Title level={5} style={{ marginTop: 20 }}>考勤明细（按考勤规则逐条计算）</Typography.Title>
            <Table
              rowKey={(r) => r.att_date + r.status}
              size="small"
              dataSource={detail.attendance_items}
              pagination={false}
              columns={[
                { title: '日期', dataIndex: 'att_date', width: 100 },
                { title: '状态', dataIndex: 'status_label', width: 80 },
                { title: '规则金额', dataIndex: 'amount', width: 90, render: money },
                {
                  title: '增减',
                  dataIndex: 'delta',
                  render: (v: string) => (
                    <span style={{ color: Number(v) < 0 ? '#cf1322' : '#3f8600' }}>{money(v)}</span>
                  ),
                },
              ]}
            />
            <Typography.Title level={5} style={{ marginTop: 20 }}>奖惩明细</Typography.Title>
            {detail.adjustment_items.length === 0 && (
              <Typography.Text type="secondary">当月无手动奖惩记录。</Typography.Text>
            )}
            {detail.adjustment_items.length > 0 && (
              <Table
                rowKey="id"
                size="small"
                dataSource={detail.adjustment_items}
                pagination={false}
                columns={[
                  {
                    title: '类型',
                    dataIndex: 'adjust_type',
                    width: 70,
                    render: (t: number) => (
                      <Tag color={t === 1 ? 'green' : 'red'}>{adjustTypeText(t)}</Tag>
                    ),
                  },
                  { title: '金额', dataIndex: 'amount', width: 90, render: money },
                  { title: '事由', dataIndex: 'reason' },
                ]}
              />
            )}
          </>
        )}
      </Drawer>
    </Card>
  )
}
