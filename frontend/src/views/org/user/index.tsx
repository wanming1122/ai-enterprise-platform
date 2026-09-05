import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  TreeSelect,
  Typography,
  Upload,
} from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { positionApi, type PositionOption } from '@/api/position'
import { saveBlob, userApi, type DeptOption, type ImportResult, type RoleOption, type UserForm } from '@/api/user'
import type { UserInfo } from '@/types'

const STATUS_TEXT: Record<number, { text: string; color: string }> = {
  1: { text: '正常', color: 'green' },
  0: { text: '停用', color: 'red' },
}

/** 部门树 → TreeSelect treeData */
function toTreeData(depts: DeptOption[]): { value: number; title: string; children?: unknown[] }[] {
  return depts.map((d) => ({
    value: d.id,
    title: d.name,
    children: d.children?.length ? (toTreeData(d.children) as unknown[]) : undefined,
  }))
}

export default function UserManage() {
  const { message } = App.useApp()
  const [form] = Form.useForm<UserForm>()
  const [filters, setFilters] = useState<{ keyword?: string; department_id?: number; role_id?: number; status?: number }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<UserInfo[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [depts, setDepts] = useState<DeptOption[]>([])
  const [roles, setRoles] = useState<RoleOption[]>([])
  const [positions, setPositions] = useState<PositionOption[]>([])
  const [editing, setEditing] = useState<UserInfo | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [importing, setImporting] = useState(false)

  const roleNameMap = useMemo(() => new Map(roles.map((r) => [r.code, r.name] as [string, string])), [roles])
  const roleIdMap = useMemo(() => new Map(roles.map((r) => [r.code, r.id] as [string, number])), [roles])

  const loadOptions = useCallback(async () => {
    try {
      const [d, r, p] = await Promise.all([userApi.departments(), userApi.roles(), positionApi.options()])
      setDepts(d)
      setRoles(r)
      setPositions(p)
    } catch {
      // 提示已由拦截器统一处理
    }
  }, [])

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await userApi.list({ ...filters, page, page_size: pageSize })
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

  const handleSearch = (values: { keyword?: string; department_id?: number; role_id?: number; status?: number }) => {
    setFilters({
      keyword: values.keyword || undefined,
      department_id: values.department_id,
      role_id: values.role_id,
      status: values.status,
    })
    setPage(1)
  }

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (record: UserInfo) => {
    setEditing(record)
    form.setFieldsValue({
      username: record.username,
      real_name: record.real_name,
      nickname: record.nickname,
      gender: record.gender ?? 0,
      birthday: record.birthday ? dayjs(record.birthday) : undefined,
      email: record.email,
      phone: record.phone,
      department_id: record.department_id ?? undefined,
      position_id: record.position_id ?? undefined,
      role_ids: (record.roles ?? []).map((code) => Number(roleIdMap.get(code)) || 0).filter(Boolean),
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    const data: UserForm = {
      ...values,
      birthday: values.birthday ? dayjs(values.birthday).format('YYYY-MM-DD') : null,
    }
    setSaving(true)
    try {
      if (editing) {
        await userApi.update(editing.id, data)
        message.success('编辑成功')
      } else {
        await userApi.create(data)
        message.success('新增成功')
      }
      setModalOpen(false)
      loadList()
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (record: UserInfo) => {
    await userApi.toggleStatus(record.id)
    message.success(record.status === 1 ? '已停用' : '已启用')
    loadList()
  }

  const handleResetPwd = async (record: UserInfo) => {
    const res = await userApi.resetPassword(record.id)
    Modal.success({
      title: '重置密码成功',
      content: `用户 ${record.username} 的临时密码为：${res.temp_password}（首次登录需修改）`,
    })
  }

  const handleRemove = async (record: UserInfo) => {
    await userApi.remove(record.id)
    message.success('删除成功')
    loadList()
  }

  const handleImport = async () => {
    if (!importFile) return
    setImporting(true)
    try {
      const res = await userApi.importUsers(importFile)
      setImportResult(res)
      if (res.success > 0) {
        message.success(`成功导入 ${res.success} 条`)
        loadList()
      }
    } finally {
      setImporting(false)
    }
  }

  const handleExport = async () => {
    const blob = await userApi.exportUsers(filters)
    saveBlob(blob, '用户数据.xlsx')
  }

  const handleTemplate = async () => {
    const blob = await userApi.downloadTemplate()
    saveBlob(blob, '用户导入模板.xlsx')
  }

  const columns = [
    { title: '账号', dataIndex: 'username', width: 120 },
    { title: '姓名', dataIndex: 'real_name', width: 100, render: (v: string) => v || '-' },
    { title: '昵称', dataIndex: 'nickname', width: 100, render: (v: string) => v || '-' },
    { title: '部门', dataIndex: 'dept_name', width: 100, render: (v: string) => v || '-' },
    {
      title: '职位',
      key: 'position',
      width: 110,
      render: (_: unknown, record: UserInfo) => record.position_name || record.post || '-',
    },
    { title: '手机', dataIndex: 'phone', width: 120, render: (v: string) => v || '-' },
    { title: '邮箱', dataIndex: 'email', width: 160, render: (v: string) => v || '-' },
    {
      title: '角色',
      dataIndex: 'roles',
      width: 140,
      render: (codes: string[] = []) =>
        codes.map((c) => <Tag key={c}>{roleNameMap.get(c) || c}</Tag>),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (s: number) => {
        const t = STATUS_TEXT[s] || { text: '未知', color: 'default' }
        return <Tag color={t.color}>{t.text}</Tag>
      },
    },
    {
      title: '最近登录',
      dataIndex: 'last_login_at',
      width: 160,
      render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: unknown, record: UserInfo) => (
        <Space size={4}>
          <HasPermission code="user:update">
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          </HasPermission>
          <HasPermission code="user:toggle">
            <Popconfirm title={record.status === 1 ? '确认停用该账号？' : '确认启用该账号？'} onConfirm={() => handleToggle(record)}>
              <Button type="link" size="small" danger={record.status === 1}>
                {record.status === 1 ? '停用' : '启用'}
              </Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="user:reset_pwd">
            <Popconfirm title="确认重置该用户密码？" onConfirm={() => handleResetPwd(record)}>
              <Button type="link" size="small">重置密码</Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="user:delete">
            <Popconfirm title="确认删除该用户？" onConfirm={() => handleRemove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Form layout="inline" onFinish={handleSearch} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="keyword">
          <Input.Search placeholder="账号/姓名/手机" allowClear style={{ width: 220 }} onSearch={(v) => handleSearch({ keyword: v })} />
        </Form.Item>
        <Form.Item name="department_id">
          <TreeSelect
            placeholder="选择部门"
            allowClear
            treeData={toTreeData(depts) as never}
            style={{ width: 180 }}
          />
        </Form.Item>
        <Form.Item name="role_id">
          <Select placeholder="选择角色" allowClear style={{ width: 140 }}>
            {roles.map((r) => (
              <Select.Option key={r.id} value={r.id}>{r.name}</Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item name="status">
          <Select placeholder="状态" allowClear style={{ width: 110 }}>
            <Select.Option value={1}>正常</Select.Option>
            <Select.Option value={0}>停用</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { form.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
          </Space>
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }} wrap>
        <HasPermission code="user:create">
          <Button type="primary" onClick={openCreate}>新增用户</Button>
        </HasPermission>
        <HasPermission code="user:import">
          <Button icon={<UploadOutlined />} onClick={() => { setImportResult(null); setImportFile(null); setImportOpen(true) }}>批量导入</Button>
        </HasPermission>
        <HasPermission code="user:export">
          <Button onClick={handleExport}>导出</Button>
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
        scroll={{ x: 1200 }}
      />

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editing ? '编辑用户' : '新增用户'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={560}
        forceRender
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="username" label="账号" rules={[{ required: true, message: '请输入账号' }]}>
            <Input disabled={!!editing} placeholder="登录账号" />
          </Form.Item>
          {!editing && (
            <Form.Item
              name="password"
              label="密码"
              rules={[
                { required: true, message: '请输入密码' },
                { pattern: /^(?=.*[A-Za-z])(?=.*\d).{8,}$/, message: '至少8位且包含字母和数字' },
              ]}
            >
              <Input.Password placeholder="至少8位且包含字母和数字" />
            </Form.Item>
          )}
          <Form.Item name="real_name" label="姓名">
            <Input placeholder="真实姓名" />
          </Form.Item>
          <Form.Item name="nickname" label="昵称">
            <Input placeholder="昵称" />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="gender" label="性别" style={{ width: 140 }}>
              <Select>
                <Select.Option value={0}>未知</Select.Option>
                <Select.Option value={1}>男</Select.Option>
                <Select.Option value={2}>女</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="birthday" label="生日" style={{ width: 180 }}>
              <DatePicker style={{ width: '100%' }} placeholder="选择日期" />
            </Form.Item>
          </Space>
          <Form.Item name="phone" label="手机">
            <Input placeholder="手机号" />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
            <Input placeholder="邮箱" />
          </Form.Item>
          <Form.Item name="department_id" label="部门">
            <TreeSelect allowClear placeholder="选择部门" treeData={toTreeData(depts) as never} />
          </Form.Item>
          <Form.Item name="position_id" label="职位" extra="选择职位后自动获得其绑定角色的权限模板">
            <Select allowClear placeholder="选择职位" showSearch optionFilterProp="label">
              {positions.map((p) => (
                <Select.Option key={p.id} value={p.id} label={p.name}>
                  {p.name}
                  {p.role_name ? `（${p.role_name}）` : ''}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="role_ids" label="角色">
            <Select mode="multiple" allowClear placeholder="选择角色">
              {roles.map((r) => (
                <Select.Option key={r.id} value={r.id}>{r.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 导入弹窗 */}
      <Modal
        title="批量导入用户"
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
            message={`共 ${importResult.total} 条，成功 ${importResult.success} 条，失败 ${importResult.failed} 条`}
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
