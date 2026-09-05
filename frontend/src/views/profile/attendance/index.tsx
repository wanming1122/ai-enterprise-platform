import { Button, Card, DatePicker, Form, Table, Tag } from 'antd'
import type { Dayjs } from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import { ATT_STATUS_OPTIONS, type AttRecordItem } from '@/api/attendance'
import { profileApi } from '@/api/profile'

const STATUS_COLOR = new Map(ATT_STATUS_OPTIONS.map((s) => [s.value, s.color]))

export default function MyAttendance() {
  const [filterForm] = Form.useForm<{ month?: Dayjs }>()
  const [month, setMonth] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<AttRecordItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await profileApi.attendance({ month, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [month, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const columns = [
    { title: '日期', dataIndex: 'att_date', width: 110 },
    { title: '签到', dataIndex: 'check_in', width: 90, render: (v: string | null) => v || '-' },
    { title: '签退', dataIndex: 'check_out', width: 90, render: (v: string | null) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string, record: AttRecordItem) => (
        <Tag color={STATUS_COLOR.get(v) || 'default'}>{record.status_label}</Tag>
      ),
    },
    { title: '地点', dataIndex: 'location', ellipsis: true, render: (v: string | null) => v || '-' },
    { title: '备注', dataIndex: 'remark', ellipsis: true, render: (v: string | null) => v || '-' },
  ]

  return (
    <Card>
      <Form
        layout="inline"
        form={filterForm}
        onFinish={(v) => { setMonth(v.month ? v.month.format('YYYY-MM') : undefined); setPage(1) }}
        style={{ marginBottom: 16, rowGap: 12 }}
      >
        <Form.Item name="month">
          <DatePicker picker="month" placeholder="选择月份" style={{ width: 140 }} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit">查询</Button>
        </Form.Item>
        <Form.Item>
          <Button onClick={() => { filterForm.resetFields(); setMonth(undefined); setPage(1) }}>重置</Button>
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
      />
    </Card>
  )
}
