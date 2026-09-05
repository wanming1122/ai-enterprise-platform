import { Button, Card, DatePicker, Descriptions, Drawer, Form, Table, Tag } from 'antd'
import type { Dayjs } from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import { profileApi } from '@/api/profile'
import type { SalaryDetail, SalaryItem } from '@/api/salary'

const STATUS_TAG: Record<number, { text: string; color: string }> = {
  0: { text: '草稿', color: 'orange' },
  1: { text: '已确认', color: 'blue' },
  2: { text: '已发放', color: 'green' },
}

const money = (v: string | null | undefined) =>
  v == null ? '-' : `¥${Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`

export default function MySalary() {
  const [filterForm] = Form.useForm<{ year_month?: Dayjs }>()
  const [yearMonth, setYearMonth] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<SalaryItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<SalaryDetail | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await profileApi.salaries({ year_month: yearMonth, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [yearMonth, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const openDetail = async (record: SalaryItem) => {
    const res = await profileApi.salaryDetail(record.id)
    setDetail(res)
    setDetailOpen(true)
  }

  const columns = [
    { title: '月份', dataIndex: 'year_month', width: 90 },
    { title: '职位', dataIndex: 'position_name', width: 120 },
    { title: '基本工资', dataIndex: 'base_salary', width: 110, render: money },
    {
      title: '考勤增减',
      dataIndex: 'attendance_adjust',
      width: 110,
      render: (v: string) => (
        <span style={{ color: Number(v) < 0 ? '#cf1322' : Number(v) > 0 ? '#3f8600' : undefined }}>{money(v)}</span>
      ),
    },
    {
      title: '手动奖惩',
      dataIndex: 'manual_adjust',
      width: 110,
      render: (v: string) => (
        <span style={{ color: Number(v) < 0 ? '#cf1322' : Number(v) > 0 ? '#3f8600' : undefined }}>{money(v)}</span>
      ),
    },
    { title: '应发合计', dataIndex: 'total_salary', width: 120, render: money },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s: number) => {
        const t = STATUS_TAG[s] || { text: '未知', color: 'default' }
        return <Tag color={t.color}>{t.text}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: SalaryItem) => (
        <Button type="link" size="small" onClick={() => openDetail(record)}>明细</Button>
      ),
    },
  ]

  return (
    <Card>
      <Form
        layout="inline"
        form={filterForm}
        onFinish={(v) => { setYearMonth(v.year_month ? v.year_month.format('YYYY-MM') : undefined); setPage(1) }}
        style={{ marginBottom: 16, rowGap: 12 }}
      >
        <Form.Item name="year_month">
          <DatePicker picker="month" placeholder="选择月份" style={{ width: 140 }} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit">查询</Button>
        </Form.Item>
        <Form.Item>
          <Button onClick={() => { filterForm.resetFields(); setYearMonth(undefined); setPage(1) }}>重置</Button>
        </Form.Item>
      </Form>
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
        scroll={{ x: 850 }}
      />

      {/* 明细抽屉 */}
      <Drawer title="我的工资单明细" open={detailOpen} onClose={() => setDetailOpen(false)} width={640}>
        {detail && (
          <>
            <Descriptions
              size="small"
              column={2}
              bordered
              items={[
                { key: 'month', label: '月份', children: detail.payroll.year_month },
                { key: 'pos', label: '职位', children: detail.payroll.position_name },
                { key: 'base', label: '① 基本工资', children: money(detail.payroll.base_salary) },
                { key: 'att', label: '② 考勤增减', children: money(detail.payroll.attendance_adjust) },
                { key: 'manual', label: '③ 手动奖惩', children: money(detail.payroll.manual_adjust) },
                { key: 'total', label: '应发合计', children: <b>{money(detail.payroll.total_salary)}</b> },
              ]}
            />
            <Table
              style={{ marginTop: 20 }}
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
            <Table
              style={{ marginTop: 16 }}
              rowKey="id"
              size="small"
              dataSource={detail.adjustment_items}
              pagination={false}
              columns={[
                {
                  title: '类型',
                  dataIndex: 'adjust_type',
                  width: 70,
                  render: (t: number) => <Tag color={t === 1 ? 'green' : 'red'}>{t === 1 ? '奖励' : '罚款'}</Tag>,
                },
                { title: '金额', dataIndex: 'amount', width: 90, render: money },
                { title: '事由', dataIndex: 'reason' },
              ]}
            />
          </>
        )}
      </Drawer>
    </Card>
  )
}
