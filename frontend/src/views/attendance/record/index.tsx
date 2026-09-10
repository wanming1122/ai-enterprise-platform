import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  TimePicker,
  TreeSelect,
  Typography,
  Upload,
} from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { ATT_STATUS_OPTIONS, attApi, type AttImportResult, type AttRecordItem } from '@/api/attendance'
import { saveBlob, userApi, type DeptOption } from '@/api/user'

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

const STATUS_COLOR = new Map(ATT_STATUS_OPTIONS.map((s) => [s.value, s.color]))

/** 手动补录表单值（日期/时间为 Dayjs，提交时格式化） */
interface CreateFormValues {
  user_id?: number
  att_date?: Dayjs
  check_in?: Dayjs | null
  check_out?: Dayjs | null
  status?: string
  location?: string
  remark?: string
}

export default function AttendanceRecord() {
  const { message } = App.useApp()
  const [filterForm] = Form.useForm<{ department_id?: number; user_id?: number; month?: Dayjs; status?: string }>()
  const [form] = Form.useForm<CreateFormValues>()
  const [filters, setFilters] = useState<{
    department_id?: number
    user_id?: number
    month?: string
    status?: string
  }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<AttRecordItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [depts, setDepts] = useState<DeptOption[]>([])
  const [users, setUsers] = useState<UserOption[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState<AttImportResult | null>(null)
  const [importing, setImporting] = useState(false)

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
      const res = await attApi.list({ ...filters, page, page_size: pageSize })
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

  const handleSearch = (values: { department_id?: number; user_id?: number; month?: Dayjs; status?: string }) => {
    setFilters({
      department_id: values.department_id,
      user_id: values.user_id,
      month: values.month ? values.month.format('YYYY-MM') : undefined,
      status: values.status,
    })
    setPage(1)
  }

  const handleCreate = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      const res = await attApi.create({
        user_id: values.user_id,
        att_date: values.att_date ? values.att_date.format('YYYY-MM-DD') : undefined,
        check_in: values.check_in ? values.check_in.format('HH:mm') : null,
        check_out: values.check_out ? values.check_out.format('HH:mm') : null,
        status: values.status,
        location: values.location,
        remark: values.remark,
      })
      message.success(res.overwritten ? '该员工当日已有记录，已覆盖更新' : '补录成功')
      setCreateOpen(false)
      form.resetFields()
      loadList()
    } finally {
      setSaving(false)
    }
  }

  const handleImport = async () => {
    if (!importFile) return
    setImporting(true)
    try {
      const res = await attApi.importRecords(importFile)
      setImportResult(res)
      if (res.success > 0) {
        message.success(`成功导入 ${res.success} 条${res.overwritten ? `，覆盖 ${res.overwritten} 条已有记录` : ''}`)
        loadList()
      }
    } finally {
      setImporting(false)
    }
  }

  const handleTemplate = async () => {
    try {
      const blob = await attApi.downloadTemplate()
      saveBlob(blob, '考勤导入模板.xlsx')
    } catch {
      // 失败提示已由下载封装统一处理
    }
  }

  const columns = [
    { title: '账号', dataIndex: 'username', width: 110 },
    { title: '姓名', dataIndex: 'real_name', width: 90, render: (v: string | null) => v || '-' },
    { title: '部门', dataIndex: 'dept_name', width: 100, render: (v: string | null) => v || '-' },
    { title: '日期', dataIndex: 'att_date', width: 105 },
    { title: '签到', dataIndex: 'check_in', width: 75, render: (v: string | null) => v || '-' },
    { title: '签退', dataIndex: 'check_out', width: 75, render: (v: string | null) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (v: string, record: AttRecordItem) => (
        <Tag color={STATUS_COLOR.get(v) || 'default'}>{record.status_label}</Tag>
      ),
    },
    { title: '地点', dataIndex: 'location', ellipsis: true, render: (v: string | null) => v || '-' },
    { title: '备注', dataIndex: 'remark', ellipsis: true, render: (v: string | null) => v || '-' },
    {
      title: '来源',
      dataIndex: 'source',
      width: 75,
      render: (v: number, record: AttRecordItem) => record.source_label || (v === 1 ? '导入' : '手动'),
    },
  ]

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={handleSearch} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="department_id">
          <TreeSelect placeholder="选择部门" allowClear treeData={toTreeData(depts) as never} style={{ width: 170 }} />
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
        <Form.Item name="month">
          <DatePicker picker="month" placeholder="选择月份" style={{ width: 130 }} />
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 110 }}>
            {ATT_STATUS_OPTIONS.map((s) => (
              <Select.Option key={s.value} value={s.value}>{s.label}</Select.Option>
            ))}
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
        <HasPermission code="attendance:create">
          <Button type="primary" onClick={() => { form.resetFields(); setCreateOpen(true) }}>手动补录</Button>
        </HasPermission>
        <HasPermission code="attendance:import">
          <Button icon={<UploadOutlined />} onClick={() => { setImportResult(null); setImportFile(null); setImportOpen(true) }}>
            导入考勤
          </Button>
          <Button onClick={handleTemplate}>下载模板</Button>
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
        scroll={{ x: 1000 }}
      />

      {/* 手动补录弹窗 */}
      <Modal
        title="手动补录考勤"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={saving}
        width={520}
        forceRender
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="user_id" label="员工" rules={[{ required: true, message: '请选择员工' }]}>
            <Select placeholder="选择员工" showSearch optionFilterProp="label">
              {users.map((u) => (
                <Select.Option key={u.id} value={u.id} label={u.username}>
                  {u.real_name ? `${u.real_name}（${u.username}）` : u.username}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="att_date" label="考勤日期" rules={[{ required: true, message: '请选择日期' }]}>
            <DatePicker style={{ width: '100%' }} placeholder="选择日期" />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="check_in" label="签到时间" style={{ width: 150 }}>
              <TimePicker format="HH:mm" style={{ width: '100%' }} placeholder="签到" />
            </Form.Item>
            <Form.Item name="check_out" label="签退时间" style={{ width: 150 }}>
              <TimePicker format="HH:mm" style={{ width: '100%' }} placeholder="签退" />
            </Form.Item>
          </Space>
          <Form.Item name="status" label="考勤状态" rules={[{ required: true, message: '请选择状态' }]}>
            <Select placeholder="选择状态">
              {ATT_STATUS_OPTIONS.map((s) => (
                <Select.Option key={s.value} value={s.value}>{s.label}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="location" label="地点">
            <Input placeholder="考勤地点" maxLength={128} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} placeholder="备注" maxLength={255} />
          </Form.Item>
          <Typography.Text type="secondary">该员工同日已有记录时将覆盖更新。</Typography.Text>
        </Form>
      </Modal>

      {/* 导入弹窗 */}
      <Modal
        title="导入考勤"
        open={importOpen}
        onCancel={() => setImportOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setImportOpen(false)}>关闭</Button>,
          <Button key="import" type="primary" loading={importing} disabled={!importFile} onClick={handleImport}>
            开始导入
          </Button>,
        ]}
      >
        <Typography.Paragraph type="secondary">
          请先 <Button type="link" size="small" onClick={handleTemplate}>下载模板</Button> 填写后上传 .xlsx 文件。
          状态列填中文（正常/迟到/早退/漏签/旷工/请假/出差）；同员工同日重复导入覆盖更新。
        </Typography.Paragraph>
        <Upload.Dragger
          accept=".xlsx"
          maxCount={1}
          beforeUpload={(file) => {
            setImportFile(file as File)
            return false
          }}
          onRemove={() => setImportFile(null)}
        >
          <p className="ant-upload-drag-icon"><UploadOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
        </Upload.Dragger>
        {importResult && (
          <Alert
            style={{ marginTop: 16 }}
            type={importResult.failed > 0 ? 'warning' : 'success'}
            showIcon
            message={`共 ${importResult.total} 条，成功 ${importResult.success} 条（覆盖 ${importResult.overwritten} 条），失败 ${importResult.failed} 条`}
            description={
              importResult.errors.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {importResult.errors.map((e, i) => (
                    <li key={i}>第 {e.row} 行：{e.reason}</li>
                  ))}
                </ul>
              ) : undefined
            }
          />
        )}
      </Modal>
    </Card>
  )
}
