import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import { logApi, type LogItem } from '@/api/log'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

interface FilterValues {
  keyword?: string
  module?: string
  result?: number
  range?: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null
}

export default function LogList() {
  const [filterForm] = Form.useForm<FilterValues>()
  const [filters, setFilters] = useState<FilterValues>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<LogItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const [start, end] = filters.range ?? []
      const { range: _range, ...rest } = filters
      const res = await logApi.list({
        ...rest,
        start_date: start ? start.format('YYYY-MM-DD') : undefined,
        end_date: end ? end.format('YYYY-MM-DD') : undefined,
        page,
        page_size: pageSize,
      })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleSearch = (values: FilterValues) => {
    setFilters({ ...values, keyword: values.keyword?.trim() || undefined })
    setPage(1)
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: '操作账号', dataIndex: 'username', width: 110, render: (v: string | null) => v || '-' },
    { title: '模块', dataIndex: 'module', width: 110, render: (v: string | null) => v || '-' },
    { title: '操作', dataIndex: 'action', width: 130, ellipsis: true, render: (v: string | null) => v || '-' },
    {
      title: '请求',
      key: 'request',
      width: 220,
      ellipsis: true,
      render: (_: unknown, r: LogItem) =>
        r.path ? (
          <Typography.Text code style={{ fontSize: 12 }}>
            {r.method} {r.path}
          </Typography.Text>
        ) : (
          '-'
        ),
    },
    {
      title: '结果',
      dataIndex: 'result',
      width: 80,
      render: (s: number, r: LogItem) =>
        s === 1 ? <Tag color="success">成功</Tag> : (
          <Tooltip title={r.error_message || '失败'}>
            <Tag color="error">失败</Tag>
          </Tooltip>
        ),
    },
    { title: '耗时', dataIndex: 'duration_ms', width: 90, render: (v: number) => `${v} ms` },
    { title: 'IP', dataIndex: 'ip', width: 120, render: (v: string | null) => v || '-' },
    { title: '时间', dataIndex: 'created_at', width: 150, render: fmtTime },
    {
      title: '参数',
      dataIndex: 'params',
      ellipsis: true,
      render: (v: string | null) =>
        v ? (
          <Tooltip title={<div style={{ maxWidth: 420, wordBreak: 'break-all' }}>{v}</div>}>
            <Typography.Text style={{ fontSize: 12 }}>{v}</Typography.Text>
          </Tooltip>
        ) : (
          '-'
        ),
    },
  ]

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={handleSearch} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="keyword">
          <Input placeholder="账号 / 操作 / 路径" allowClear style={{ width: 190 }} />
        </Form.Item>
        <Form.Item name="module">
          <Input placeholder="模块（如 NL2SQL）" allowClear style={{ width: 150 }} />
        </Form.Item>
        <Form.Item name="result">
          <Select placeholder="结果" allowClear style={{ width: 100 }} options={[
            { value: 1, label: '成功' },
            { value: 0, label: '失败' },
          ]} />
        </Form.Item>
        <Form.Item name="range">
          <DatePicker.RangePicker placeholder={['开始日期', '结束日期']} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={loadList}>刷新</Button>
          </Space>
        </Form.Item>
      </Form>

      <Row style={{ marginBottom: 12 }}>
        <Col span={24}>
          <Typography.Text type="secondary">
            审计日志由系统自动记录（登录、越权拦截、关键业务操作），只读不可修改。
          </Typography.Text>
        </Col>
      </Row>

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
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
        scroll={{ x: 1300 }}
      />
    </Card>
  )
}
