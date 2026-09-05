import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tree,
} from 'antd'
import { useCallback, useEffect, useMemo, useState, type Key } from 'react'
import HasPermission from '@/components/HasPermission'
import { ROLE_TYPE_TEXT, roleApi, type RoleForm, type RoleItem } from '@/api/role'
import { menuApi, type MenuItem2 } from '@/api/menu'

/** 菜单树 → Tree treeData */
function toTreeData(nodes: MenuItem2[]): { key: number; title: string; children?: unknown[] }[] {
  return nodes.map((n) => ({
    key: n.id,
    title: n.name,
    children: n.children?.length ? (toTreeData(n.children) as unknown[]) : undefined,
  }))
}

export default function RoleManage() {
  const { message } = App.useApp()
  const [form] = Form.useForm<RoleForm>()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<RoleItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<RoleItem | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [authTarget, setAuthTarget] = useState<RoleItem | null>(null)
  const [menuTree, setMenuTree] = useState<MenuItem2[]>([])
  const [checkedKeys, setCheckedKeys] = useState<Key[]>([])
  const [authSaving, setAuthSaving] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await roleApi.list({ keyword: keyword || undefined, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (record: RoleItem) => {
    setEditing(record)
    form.setFieldsValue({
      name: record.name,
      code: record.code,
      role_type: record.role_type,
      description: record.description,
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      if (editing) {
        await roleApi.update(editing.id, values)
        message.success('编辑成功')
      } else {
        await roleApi.create(values)
        message.success('新增成功')
      }
      setModalOpen(false)
      loadList()
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (record: RoleItem) => {
    await roleApi.toggleStatus(record.id)
    message.success(record.status === 1 ? '已停用' : '已启用')
    loadList()
  }

  const handleRemove = async (record: RoleItem) => {
    await roleApi.remove(record.id)
    message.success('删除成功')
    loadList()
  }

  const openAuth = async (record: RoleItem) => {
    setAuthTarget(record)
    setCheckedKeys([])
    const [tree, ids] = await Promise.all([menuApi.tree(), roleApi.menus(record.id)])
    setMenuTree(tree)
    setCheckedKeys(ids)
  }

  const submitAuth = async () => {
    if (!authTarget) return
    setAuthSaving(true)
    try {
      await roleApi.authorize(authTarget.id, checkedKeys as number[])
      message.success('授权成功')
      setAuthTarget(null)
    } finally {
      setAuthSaving(false)
    }
  }

  const treeData = useMemo(() => toTreeData(menuTree), [menuTree])

  const columns = [
    { title: '角色名称', dataIndex: 'name', width: 140 },
    { title: '角色编码', dataIndex: 'code', width: 130 },
    {
      title: '类型',
      dataIndex: 'role_type',
      width: 110,
      render: (t: number) => <Tag>{ROLE_TYPE_TEXT[t] || '未知'}</Tag>,
    },
    { title: '描述', dataIndex: 'description', render: (v: string) => v || '-' },
    { title: '绑定用户数', dataIndex: 'user_count', width: 100 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (s: number) => (s === 1 ? <Tag color="green">启用</Tag> : <Tag color="red">停用</Tag>),
    },
    {
      title: '操作',
      key: 'action',
      width: 230,
      render: (_: unknown, record: RoleItem) => (
        <Space size={4}>
          <HasPermission code="role:update">
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          </HasPermission>
          <HasPermission code="role:authorize">
            <Button type="link" size="small" onClick={() => openAuth(record)}>菜单授权</Button>
          </HasPermission>
          <HasPermission code="role:update">
            <Popconfirm title={record.status === 1 ? '确认停用该角色？' : '确认启用该角色？'} onConfirm={() => handleToggle(record)}>
              <Button type="link" size="small" danger={record.status === 1}>
                {record.status === 1 ? '停用' : '启用'}
              </Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="role:delete">
            <Popconfirm title="确认删除该角色？" onConfirm={() => handleRemove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="角色名称/编码"
          allowClear
          style={{ width: 220 }}
          onSearch={(v) => { setKeyword(v); setPage(1) }}
        />
        <HasPermission code="role:create">
          <Button type="primary" onClick={openCreate}>新增角色</Button>
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
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps) },
        }}
        scroll={{ x: 900 }}
      />

      <Modal
        title={editing ? '编辑角色' : '新增角色'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={480}
        forceRender
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="角色名称" rules={[{ required: true, message: '请输入角色名称' }]}>
            <Input placeholder="角色名称" maxLength={64} />
          </Form.Item>
          <Form.Item
            name="code"
            label="角色编码"
            rules={[
              { required: true, message: '请输入角色编码' },
              { pattern: /^[A-Za-z][A-Za-z0-9_]*$/, message: '以字母开头，仅含字母数字下划线' },
            ]}
          >
            <Input placeholder="如 admin、employee" maxLength={32} disabled={!!editing} />
          </Form.Item>
          <Form.Item name="role_type" label="角色类型">
            <Select>
              <Select.Option value={2}>普通管理员</Select.Option>
              <Select.Option value={3}>普通员工</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="角色描述" maxLength={255} rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`菜单授权：${authTarget?.name || ''}`}
        open={!!authTarget}
        onOk={submitAuth}
        onCancel={() => setAuthTarget(null)}
        confirmLoading={authSaving}
        width={520}
      >
        <Tree
          checkable
          selectable={false}
          defaultExpandAll
          checkedKeys={checkedKeys}
          onCheck={(keys) => setCheckedKeys(keys as Key[])}
          treeData={treeData as never}
        />
      </Modal>
    </Card>
  )
}
