import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import {
  nl2sqlApi,
  REVIEW_STATUS_COLOR,
  REVIEW_STATUS_OPTIONS,
  type NL2SQLRecordItem,
} from '@/api/nl2sql'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

export default function NL2SQLHistory() {
  const [filterForm] = Form.useForm<{ keyword?: string; status?: number }>()
  const [filters, setFilters] = useState<{ keyword?: string; status?: number }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<NL2SQLRecordItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [detail, setDetail] = useState<NL2SQLRecordItem | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await nl2sqlApi.history({ ...filters, page, page_size: pageSize })
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

  const openDetail = async (record: NL2SQLRecordItem) => {
    setDetail(record)
    setDetailOpen(true)
    if (record.review_status === 3 && !record.result) {
      try {
        setDetail(await nl2sqlApi.detail(record.id))
      } catch {
        // 保留列表行数据展示
      }
    }
  }

  const resultColumns = (detail?.result?.columns ?? []).map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    ellipsis: true,
    render: (v: unknown) => (v == null ? '-' : String(v)),
  }))

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '用户', dataIndex: 'username', width: 100, render: (v: string | null) => v || '-' },
    { title: '原句', dataIndex: 'question', ellipsis: true },
    {
      title: '生成 SQL',
      dataIndex: 'generated_sql',
      ellipsis: true,
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: '状态',
      dataIndex: 'review_status',
      width: 90,
      render: (s: number, r: NL2SQLRecordItem) => (
        <Tag color={REVIEW_STATUS_COLOR[s]}>{r.review_status_label}</Tag>
      ),
    },
    {
      title: '结果行数',
      dataIndex: 'result_count',
      width: 95,
      render: (v: number | null) => (v != null ? `${v} 行` : '-'),
    },
    {
      title: '耗时',
      dataIndex: 'execution_ms',
      width: 95,
      render: (v: number | null) => (v != null ? `${v} ms` : '-'),
    },
    { title: '提问时间', dataIndex: 'created_at', width: 140, render: fmtTime },
    { title: '执行时间', dataIndex: 'executed_at', width: 140, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 80,
      fixed: 'right' as const,
      render: (_: unknown, record: NL2SQLRecordItem) => (
        <Button type="link" size="small" onClick={() => openDetail(record)}>详情</Button>
      ),
    },
  ]

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={handleSearch} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="keyword">
          <Input placeholder="按原句搜索" allowClear style={{ width: 220 }} />
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 120 }} options={REVIEW_STATUS_OPTIONS} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
          </Space>
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={loadList}>刷新</Button>
      </Space>

      <Table
        rowKey="id"
        size="middle"
        columns={columns}
        dataSource={list}
        loading={loading}
        onRow={(record) => ({ onClick: () => openDetail(record), style: { cursor: 'pointer' } })}
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
        scroll={{ x: 1250 }}
      />

      {/* 详情抽屉：原句 / SQL / 审核信息 / 完整结果表格 */}
      <Drawer
        title={`查询详情 #${detail?.id ?? ''}`}
        width={760}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        destroyOnHidden
      >
        {detail && (
          <>
            <Descriptions
              size="small"
              column={2}
              bordered
              style={{ marginBottom: 16 }}
              items={[
                { key: 'user', label: '提问人', children: detail.username || '-' },
                {
                  key: 'status',
                  label: '状态',
                  children: (
                    <Tag color={REVIEW_STATUS_COLOR[detail.review_status]}>
                      {detail.review_status_label}
                    </Tag>
                  ),
                },
                { key: 'created', label: '提问时间', children: fmtTime(detail.created_at) },
                {
                  key: 'executed',
                  label: '执行时间',
                  children: detail.executed_at ? fmtTime(detail.executed_at) : '-',
                },
                {
                  key: 'ms',
                  label: '执行耗时',
                  children: detail.execution_ms != null ? `${detail.execution_ms} ms` : '-',
                  span: 2,
                },
                { key: 'question', label: '原句', children: detail.question, span: 2 },
                {
                  key: 'sql',
                  label: '生成 SQL',
                  children: <Typography.Text code copyable>{detail.generated_sql}</Typography.Text>,
                  span: 2,
                },
                {
                  key: 'comment',
                  label: '审核意见',
                  children: detail.review_comment || '-',
                  span: 2,
                },
              ]}
            />
            <Typography.Title level={5} style={{ marginTop: 0 }}>
              执行结果{detail.result_count != null ? `（共 ${detail.result_count} 行）` : ''}
            </Typography.Title>
            {detail.result?.rows?.length ? (
              <Table
                rowKey={(_, idx) => String(idx)}
                size="small"
                columns={resultColumns}
                dataSource={detail.result.rows}
                scroll={{ x: 'max-content' }}
                pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 行`, size: 'small' }}
              />
            ) : (
              <Typography.Text type="secondary">
                {detail.review_status === 3 ? '查询结果为空' : '尚未执行，暂无结果'}
              </Typography.Text>
            )}
          </>
        )}
      </Drawer>
    </Card>
  )
}
