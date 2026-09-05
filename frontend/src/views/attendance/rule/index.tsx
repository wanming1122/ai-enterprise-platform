import { App, Button, Card, InputNumber, Radio, Space, Switch, Table, Tag, Typography } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { attApi, type AttRuleItem } from '@/api/attendance'

/** 行内编辑中的草稿值 */
interface RuleDraft {
  adjust_type: number
  amount: number
  enabled: number
}

export default function AttendanceRule() {
  const { message } = App.useApp()
  const [rules, setRules] = useState<AttRuleItem[]>([])
  const [drafts, setDrafts] = useState<Record<number, RuleDraft>>({})
  const [savingId, setSavingId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  const loadRules = useCallback(async () => {
    setLoading(true)
    try {
      const res = await attApi.rules()
      setRules(res)
      setDrafts(
        Object.fromEntries(res.map((r) => [r.id, { adjust_type: r.adjust_type, amount: Number(r.amount), enabled: r.enabled }])),
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadRules()
  }, [loadRules])

  const updateDraft = (id: number, patch: Partial<RuleDraft>) => {
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }))
  }

  const handleSave = async (record: AttRuleItem) => {
    const draft = drafts[record.id]
    setSavingId(record.id)
    try {
      await attApi.updateRule(record.id, {
        adjust_type: draft.adjust_type,
        amount: draft.amount,
        enabled: draft.enabled,
      })
      message.success(`规则「${record.status_label}」已保存`)
      loadRules()
    } finally {
      setSavingId(null)
    }
  }

  const columns = [
    { title: '考勤状态', dataIndex: 'status_label', width: 120 },
    {
      title: '调整类型',
      dataIndex: 'adjust_type',
      width: 180,
      render: (_: unknown, record: AttRuleItem) => (
        <Radio.Group
          size="small"
          value={drafts[record.id]?.adjust_type}
          onChange={(e) => updateDraft(record.id, { adjust_type: e.target.value })}
        >
          <Radio.Button value={1}>奖励</Radio.Button>
          <Radio.Button value={2}>扣款</Radio.Button>
        </Radio.Group>
      ),
    },
    {
      title: '每次/每日金额',
      dataIndex: 'amount',
      width: 180,
      render: (_: unknown, record: AttRuleItem) => (
        <InputNumber
          min={0}
          precision={2}
          value={drafts[record.id]?.amount}
          onChange={(v) => updateDraft(record.id, { amount: v ?? 0 })}
          addonAfter="¥"
          style={{ width: 150 }}
        />
      ),
    },
    {
      title: '参与薪资计算',
      dataIndex: 'enabled',
      width: 130,
      render: (_: unknown, record: AttRuleItem) => (
        <Switch
          checked={drafts[record.id]?.enabled === 1}
          onChange={(checked) => updateDraft(record.id, { enabled: checked ? 1 : 0 })}
        />
      ),
    },
    { title: '更新时间', dataIndex: 'updated_at', width: 170, render: (v: string | null) => (v ? v.replace('T', ' ').slice(0, 19) : '-') },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: AttRuleItem) => (
        <HasPermission code="attendance_rule:update">
          <Button type="link" size="small" loading={savingId === record.id} onClick={() => handleSave(record)}>
            保存
          </Button>
        </HasPermission>
      ),
    },
  ]

  return (
    <Card>
      <Space direction="vertical" size={4} style={{ marginBottom: 16 }}>
        <Typography.Text type="secondary">
          规则决定生成工资单时每条考勤记录的增减金额；停用（不参与计算）的状态不会影响薪资。
        </Typography.Text>
        <Typography.Text type="secondary">
          <Tag color="orange">迟到/早退</Tag>按次计算，<Tag color="red">旷工</Tag>按日计算，金额由本页维护。
        </Typography.Text>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={rules}
        loading={loading}
        pagination={false}
      />
    </Card>
  )
}
