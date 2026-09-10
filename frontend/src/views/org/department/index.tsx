import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  TreeSelect,
} from 'antd'
import { ArrowDownOutlined, ArrowUpOutlined, PlusOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useMemo, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { deptApi, type DeptForm, type DeptItem, type DeptSortItem, type UserOption } from '@/api/department'

/** 部门树 → TreeSelect treeData */
function toTreeData(nodes: DeptItem[]): { value: number; title: string; children?: unknown[] }[] {
  return nodes.map((n) => ({
    value: n.id,
    title: n.name,
    children: n.children?.length ? (toTreeData(n.children) as unknown[]) : undefined,
  }))
}

/** 深拷贝部门树 */
function deepClone(nodes: DeptItem[]): DeptItem[] {
  return nodes.map((n) => ({ ...n, children: n.children ? deepClone(n.children) : undefined }))
}

/** 在树中定位节点所在同级数组 */
function findTarget(nodes: DeptItem[], id: number): { siblings: DeptItem[]; index: number } | null {
  for (let i = 0; i < nodes.length; i++) {
    if (nodes[i].id === id) return { siblings: nodes, index: i }
    const children = nodes[i].children
    if (children && children.length > 0) {
      const r = findTarget(children, id)
      if (r) return r
    }
  }
  return null
}

/** 同级内上移/下移 */
function moveNode(nodes: DeptItem[], id: number, dir: -1 | 1): DeptItem[] {
  const clone = deepClone(nodes)
  const found = findTarget(clone, id)
  if (!found) return clone
  const { siblings, index } = found
  const target = index + dir
  if (target < 0 || target >= siblings.length) return clone
  const [item] = siblings.splice(index, 1)
  siblings.splice(target, 0, item)
  return clone
}

/** 展平树为全量排序提交数据（同级按展示顺序） */
function flattenSort(nodes: DeptItem[]): DeptSortItem[] {
  const result: DeptSortItem[] = []
  nodes.forEach((n, i) => {
    result.push({ id: n.id, sort_order: i + 1 })
    if (n.children?.length) result.push(...flattenSort(n.children))
  })
  return result
}

/** 编辑/上级下拉时排除自身子树，防止循环 */
function excludeSubtree(nodes: DeptItem[], excludeId?: number): DeptItem[] {
  if (!excludeId) return nodes
  return nodes
    .filter((n) => n.id !== excludeId)
    .map((n) => ({ ...n, children: n.children ? excludeSubtree(n.children, excludeId) : undefined }))
}

/** 收集全部节点 ID（用于始终展开树） */
function collectIds(nodes: DeptItem[]): number[] {
  return nodes.flatMap((n) => [n.id, ...(n.children ? collectIds(n.children) : [])])
}

export default function DepartmentManage() {
  const { message } = App.useApp()
  const [form] = Form.useForm<DeptForm>()
  const [depts, setDepts] = useState<DeptItem[]>([])
  const [users, setUsers] = useState<UserOption[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<DeptItem | null>(null)
  const [saving, setSaving] = useState(false)

  const loadTree = useCallback(async () => {
    setLoading(true)
    try {
      const tree = await deptApi.tree()
      setDepts(tree)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTree()
    deptApi.users().then(setUsers).catch(() => undefined)
  }, [loadTree])

  const parentOptions = useMemo(() => excludeSubtree(depts, editing?.id), [depts, editing])
  const expandedKeys = useMemo(() => collectIds(depts), [depts])

  const openCreate = (parentId?: number) => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ parent_id: parentId ?? null, status: 1, sort_order: 1 })
    setModalOpen(true)
  }

  const openEdit = (record: DeptItem) => {
    setEditing(record)
    form.setFieldsValue({
      name: record.name,
      parent_id: record.parent_id ?? null,
      leader_id: record.leader_id ?? null,
      phone: record.phone,
      email: record.email,
      description: record.description,
      sort_order: record.sort_order ?? 1,
      status: record.status ?? 1,
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      if (editing) {
        await deptApi.update(editing.id, values)
        message.success('编辑成功')
      } else {
        await deptApi.create(values)
        message.success('新增成功')
      }
      setModalOpen(false)
      loadTree()
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (record: DeptItem) => {
    await deptApi.toggleStatus(record.id)
    message.success(record.status === 1 ? '已停用' : '已启用')
    loadTree()
  }

  const handleRemove = async (record: DeptItem) => {
    try {
      await deptApi.remove(record.id)
      message.success('删除成功')
      loadTree()
    } catch {
      // 已由拦截器提示（存在下级部门/挂有员工等）
    }
  }

  const handleMove = async (id: number, dir: -1 | 1) => {
    const next = moveNode(depts, id, dir)
    setDepts(next)
    try {
      await deptApi.sort(flattenSort(next))
    } catch {
      loadTree() // 排序保存失败时回滚
    }
  }

  const columns = [
    { title: '部门名称', dataIndex: 'name', width: 200 },
    { title: '负责人', dataIndex: 'leader_name', width: 100, render: (v: string) => v || '-' },
    { title: '联系电话', dataIndex: 'phone', width: 130, render: (v: string) => v || '-' },
    { title: '邮箱', dataIndex: 'email', width: 170, render: (v: string) => v || '-' },
    { title: '描述', dataIndex: 'description', width: 180, render: (v: string) => v || '-' },
    { title: '排序', dataIndex: 'sort_order', width: 60 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (s: number) => (s === 1 ? <Tag color="green">启用</Tag> : <Tag color="red">停用</Tag>),
    },
    {
      title: '操作',
      key: 'action',
      width: 300,
      render: (_: unknown, record: DeptItem) => (
        <Space size={4}>
          <HasPermission code="dept:create">
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => openCreate(record.id)}>
              新增下级
            </Button>
          </HasPermission>
          <HasPermission code="dept:update">
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          </HasPermission>
          <HasPermission code="dept:sort">
            <Button type="link" size="small" icon={<ArrowUpOutlined />} disabled={!canMove(depts, record.id, -1)} onClick={() => handleMove(record.id, -1)} />
            <Button type="link" size="small" icon={<ArrowDownOutlined />} disabled={!canMove(depts, record.id, 1)} onClick={() => handleMove(record.id, 1)} />
          </HasPermission>
          <HasPermission code="dept:toggle">
            <Popconfirm title={record.status === 1 ? '确认停用该部门？' : '确认启用该部门？'} onConfirm={() => handleToggle(record)}>
              <Button type="link" size="small" danger={record.status === 1}>
                {record.status === 1 ? '停用' : '启用'}
              </Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="dept:delete">
            <Popconfirm title="确认删除该部门？" onConfirm={() => handleRemove(record)}>
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
        <HasPermission code="dept:create">
          <Button type="primary" onClick={() => openCreate()}>新增顶级部门</Button>
        </HasPermission>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={depts}
        loading={loading}
        pagination={false}
        expandable={{ expandedRowKeys: expandedKeys }}
        scroll={{ x: 1100 }}
      />

      <Modal
        title={editing ? '编辑部门' : '新增部门'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={520}
        forceRender
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="部门名称" rules={[{ required: true, message: '请输入部门名称' }]}>
            <Input placeholder="部门名称" maxLength={64} />
          </Form.Item>
          <Form.Item name="parent_id" label="上级部门" extra="不选择则为顶级部门">
            <TreeSelect allowClear placeholder="选择上级部门" treeData={toTreeData(parentOptions) as never} />
          </Form.Item>
          <Form.Item name="leader_id" label="部门负责人">
            <Select allowClear showSearch optionFilterProp="label" placeholder="选择负责人">
              {users.map((u) => (
                <Select.Option key={u.id} value={u.id} label={`${u.real_name || u.username}（${u.username}）`}>
                  {u.real_name || u.username}（{u.username}）
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="phone" label="联系电话">
            <Input placeholder="联系电话" maxLength={20} />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
            <Input placeholder="邮箱" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="部门描述" maxLength={255} rows={2} />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="sort_order" label="排序序号">
              <InputNumber min={0} max={999} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="status" label="状态" initialValue={1}>
              <Select style={{ width: 120 }}>
                <Select.Option value={1}>启用</Select.Option>
                <Select.Option value={0}>停用</Select.Option>
              </Select>
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  )
}

/** 判断某节点在树中是否还能上移/下移 */
function canMove(nodes: DeptItem[], id: number, dir: -1 | 1): boolean {
  const found = findTarget(nodes, id)
  if (!found) return false
  const target = found.index + dir
  return target >= 0 && target < found.siblings.length
}
