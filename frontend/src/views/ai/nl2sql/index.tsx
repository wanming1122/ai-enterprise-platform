import {
  App,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import {
  nl2sqlApi,
  REVIEW_STATUS_COLOR,
  REVIEW_STATUS_OPTIONS,
  type NL2SQLRecordItem,
  type ReviewAction,
} from '@/api/nl2sql'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

/** 右侧结果区状态说明 */
function resultHint(current: NL2SQLRecordItem | null): string {
  if (!current) return '输入自然语言并点击「生成 SQL」'
  switch (current.review_status) {
    case 0:
      return '已生成 SQL，等待审核'
    case 1:
      return '审核通过，可执行查询'
    case 2:
      return '该 SQL 已被驳回，不可执行'
    case 3:
      return `已执行 · 共 ${current.result_count ?? 0} 行 · 耗时 ${current.execution_ms ?? '-'} ms`
    default:
      return ''
  }
}

export default function NL2SQL() {
  const { message } = App.useApp()

  const [question, setQuestion] = useState('')
  const [current, setCurrent] = useState<NL2SQLRecordItem | null>(null)
  const [generating, setGenerating] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [reviewAction, setReviewAction] = useState<ReviewAction | null>(null)
  /** 本次审核的目标记录：列表行按钮传行记录，流程区按钮传 current，确定时以此为准 */
  const [reviewTarget, setReviewTarget] = useState<NL2SQLRecordItem | null>(null)
  const [reviewComment, setReviewComment] = useState('')
  const [reviewSaving, setReviewSaving] = useState(false)

  // 记录列表（默认看待审核）
  const [filterStatus, setFilterStatus] = useState<number | undefined>(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [list, setList] = useState<NL2SQLRecordItem[]>([])
  const [total, setTotal] = useState(0)
  const [listLoading, setListLoading] = useState(false)
  const [quickIds, setQuickIds] = useState<number | null>(null)

  const loadList = useCallback(async () => {
    setListLoading(true)
    try {
      const res = await nl2sqlApi.records({ status: filterStatus, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setListLoading(false)
    }
  }, [filterStatus, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleGenerate = async () => {
    const q = question.trim()
    if (q.length < 2) {
      message.warning('请输入要查询的自然语言问题')
      return
    }
    setGenerating(true)
    try {
      const rec = await nl2sqlApi.generate(q)
      setCurrent(rec)
      message.success('SQL 生成成功，等待审核')
      setPage(1)
      loadList()
    } catch {
      // 生成失败（含非法 SQL 被拒绝）已由拦截器提示
    } finally {
      setGenerating(false)
    }
  }

  const openReview = (action: ReviewAction, record?: NL2SQLRecordItem) => {
    const target = record ?? current
    if (!target || target.review_status !== 0) return
    setReviewTarget(target)
    setReviewAction(action)
    setReviewComment('')
  }

  const handleReviewOk = async () => {
    if (!reviewTarget || !reviewAction) return
    setReviewSaving(true)
    try {
      const rec = await nl2sqlApi.review(reviewTarget.id, reviewAction, reviewComment.trim() || undefined)
      setCurrent((prev) => (prev && prev.id === rec.id ? rec : prev))
      message.success(reviewAction === 'approve' ? '已通过' : '已驳回')
      setReviewAction(null)
      setReviewTarget(null)
      loadList()
    } catch {
      // 已由拦截器提示
    } finally {
      setReviewSaving(false)
    }
  }

  const handleExecute = async (record?: NL2SQLRecordItem) => {
    const target = record ?? current
    if (!target) return
    if (target.review_status === 3) {
      message.warning('该记录已执行，禁止重复执行')
      return
    }
    if (target.review_status !== 1) {
      message.warning('仅审核通过的 SQL 可执行')
      return
    }
    setExecuting(true)
    setQuickIds(target.id)
    try {
      const rec = await nl2sqlApi.execute(target.id)
      setCurrent(rec)
      message.success(`执行成功，耗时 ${rec.execution_ms ?? '-'} ms`)
      loadList()
    } catch {
      // 已由拦截器提示
    } finally {
      setExecuting(false)
      setQuickIds(null)
    }
  }

  /** 列表「查看」：载入到上方流程区；已执行记录补充拉取完整结果 */
  const handleView = async (record: NL2SQLRecordItem) => {
    setCurrent(record)
    if (record.review_status === 3 && !record.result) {
      try {
        const detail = await nl2sqlApi.detail(record.id)
        setCurrent(detail)
      } catch {
        // 无查询历史权限等场景：保留列表行数据展示
      }
    }
  }

  const reviewButtons = (record: NL2SQLRecordItem | null, compact = false) => (
    <HasPermission code="nl2sql:review">
      <Button
        type="link"
        size="small"
        icon={compact ? undefined : <CheckCircleOutlined />}
        disabled={!record || record.review_status !== 0}
        onClick={() => openReview('approve', record ?? undefined)}
      >
        通过
      </Button>
      <Button
        type="link"
        size="small"
        danger
        icon={compact ? undefined : <CloseCircleOutlined />}
        disabled={!record || record.review_status !== 0}
        onClick={() => openReview('reject', record ?? undefined)}
      >
        驳回
      </Button>
    </HasPermission>
  )

  const executeButton = (record: NL2SQLRecordItem | null, loading: boolean) => {
    const disabled = !record || record.review_status !== 1
    const tip = !record
      ? '先生成或选择一条记录'
      : record.review_status === 3
        ? '已执行，禁止重复执行'
        : record.review_status === 0
          ? '未审核，审核通过后方可执行'
          : record.review_status === 2
            ? '已驳回，不可执行'
            : ''
    return (
      <HasPermission code="nl2sql:execute">
        <Tooltip title={disabled ? tip : '只读执行，最多返回 100 行'}>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            disabled={disabled}
            loading={loading}
            onClick={() => handleExecute()}
          >
            执行 SQL
          </Button>
        </Tooltip>
      </HasPermission>
    )
  }

  const resultColumns = (current?.result?.columns ?? []).map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    ellipsis: true,
    render: (v: unknown) => (v == null ? '-' : String(v)),
  }))

  const listColumns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '提问时间', dataIndex: 'created_at', width: 140, render: fmtTime },
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
      title: '操作',
      key: 'action',
      width: 230,
      render: (_: unknown, record: NL2SQLRecordItem) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => handleView(record)}>查看</Button>
          {reviewButtons(record, true)}
          <HasPermission code="nl2sql:execute">
            <Tooltip
              title={
                record.review_status === 3
                  ? '已执行，禁止重复执行'
                  : record.review_status !== 1
                    ? '未审核，审核通过后方可执行'
                    : ''
              }
            >
              <Button
                type="link"
                size="small"
                disabled={record.review_status !== 1}
                loading={quickIds === record.id && executing}
                onClick={() => handleExecute(record)}
              >
                执行
              </Button>
            </Tooltip>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Row gutter={16}>
        {/* 左栏：自然语言 → SQL → 审核 */}
        <Col xs={24} lg={10}>
          <Card
            title="自然语言查询"
            style={{ marginBottom: 16 }}
            styles={{ body: { paddingTop: 12 } }}
          >
            <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
              NL2SQL 生成、审核与执行（仅查询 product 表，最多返回 100 行）
            </Typography.Paragraph>
            <Typography.Text strong>问题</Typography.Text>
            <Input.TextArea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="例如：库存大于100的产品按价格倒序"
              rows={3}
              showCount
              maxLength={1000}
              style={{ marginTop: 4, marginBottom: 12 }}
            />
            <Typography.Text strong>SQL</Typography.Text>
            <pre
              style={{
                marginTop: 4,
                marginBottom: 12,
                minHeight: 72,
                padding: 12,
                borderRadius: 8,
                background: '#0d1117',
                color: current?.generated_sql ? '#7ee787' : '#8b949e',
                fontSize: 13,
                lineHeight: 1.7,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {current?.generated_sql || '点击「生成 SQL」由 AI 生成查询语句'}
            </pre>
            {current && (
              <Space size={8} style={{ marginBottom: 12 }} wrap>
                <Tag color={REVIEW_STATUS_COLOR[current.review_status]}>
                  {current.review_status_label}
                </Tag>
                {current.review_comment && (
                  <Typography.Text type="secondary">
                    审核意见：{current.review_comment}
                  </Typography.Text>
                )}
              </Space>
            )}
            <div style={{ textAlign: 'right' }}>
              <Space>
                <Button
                  icon={<ThunderboltOutlined />}
                  type="primary"
                  loading={generating}
                  onClick={handleGenerate}
                >
                  生成 SQL
                </Button>
                {reviewButtons(current)}
                {executeButton(current, executing)}
              </Space>
            </div>
          </Card>
        </Col>

        {/* 右栏：查询结果 */}
        <Col xs={24} lg={14}>
          <Card title="查询结果" style={{ marginBottom: 16 }}>
            <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
              {resultHint(current)}
            </Typography.Paragraph>
            {current?.result?.rows?.length ? (
              <Table
                rowKey={(_, idx) => String(idx)}
                size="small"
                columns={resultColumns}
                dataSource={current.result.rows}
                scroll={{ x: 'max-content' }}
                pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 行`, size: 'small' }}
              />
            ) : (
              <Empty description={current?.review_status === 3 ? '查询结果为空' : '暂无结果'} />
            )}
          </Card>
        </Col>
      </Row>

      {/* 记录列表（待审核列表） */}
      <Card title="查询记录">
        <Space style={{ marginBottom: 12 }}>
          <Select
            value={filterStatus}
            onChange={(v) => {
              setFilterStatus(v)
              setPage(1)
            }}
            style={{ width: 130 }}
            allowClear
            placeholder="全部状态"
            options={REVIEW_STATUS_OPTIONS}
          />
          <Button icon={<ReloadOutlined />} onClick={loadList}>刷新</Button>
        </Space>
        <Table
          rowKey="id"
          size="middle"
          columns={listColumns}
          dataSource={list}
          loading={listLoading}
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
      </Card>

      {/* 通过/驳回弹窗（意见可选） */}
      <Modal
        title={reviewAction === 'approve' ? '通过该 SQL' : '驳回该 SQL'}
        open={reviewAction !== null}
        onOk={handleReviewOk}
        onCancel={() => {
          setReviewAction(null)
          setReviewTarget(null)
        }}
        confirmLoading={reviewSaving}
        okText={reviewAction === 'approve' ? '确认通过' : '确认驳回'}
        okButtonProps={reviewAction === 'reject' ? { danger: true } : undefined}
        width={460}
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary">
          {reviewAction === 'approve'
            ? '通过后可执行该 SQL（只读，最多返回 100 行）。'
            : '驳回后该 SQL 不可执行。'}
        </Typography.Paragraph>
        <Input.TextArea
          value={reviewComment}
          onChange={(e) => setReviewComment(e.target.value)}
          placeholder="审核意见（可选）"
          rows={3}
          maxLength={255}
        />
      </Modal>
    </div>
  )
}
