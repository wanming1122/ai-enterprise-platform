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
  Switch,
  Table,
  Tag,
  TreeSelect,
} from 'antd'
import { ArrowDownOutlined, ArrowUpOutlined, PlusOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useMemo, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { MENU_TYPE_TEXT, menuApi, type MenuForm, type MenuItem2, type MenuSortItem, type PermItem } from '@/api/menu'

function toTreeData(nodes: MenuItem2[], excludeId?: number): { value: number; title: string; children?: unknown[] }[] {
  return nodes
    .filter((n) => n.id !== excludeId)
    .map((n) => ({
      value: n.id,
      title: n.name,
      children: n.children?.length ? (toTreeData(n.children, excludeId) as unknown[]) : undefined,
    }))
}

function deepClone(nodes: MenuItem2[]): MenuItem2[] {
  return nodes.map((n) => ({ ...n, children: n.children ? deepClone(n.children) : undefined }))
}

function findTarget(nodes: MenuItem2[], id: number): { siblings: MenuItem2[]; index: number } | null {
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

function moveNode(nodes: MenuItem2[], id: number, dir: -1 | 1): MenuItem2[] {
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

function flattenSort(nodes: MenuItem2[]): MenuSortItem[] {
  const result: MenuSortItem[] = []
  nodes.forEach((n, i) => {
    result.push({ id: n.id, sort_order: i + 1 })
    if (n.children?.length) result.push(...flattenSort(n.children))
  })
  return result
}

function collectIds(nodes: MenuItem2[]): number[] {
  return nodes.flatMap((n) => [n.id, ...(n.children ? collectIds(n.children) : [])])
}

function canMove(nodes: MenuItem2[], id: number, dir: -1 | 1): boolean {
  const found = findTarget(nodes, id)
  if (!found) return false
  const target = found.index + dir
  return target >= 0 && target < found.siblings.length
}

export default function MenuManage() {
  const { message } = App.useApp()
  const [form] = Form.useForm<MenuForm>()
  const [menus, setMenus] = useState<MenuItem2[]>([])
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<MenuItem2 | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [permOpen, setPermOpen] = useState(false)

  const loadTree = useCallback(async () => {
    setLoading(true)
    try {
      setMenus(await menuApi.tree())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTree()
  }, [loadTree])

  const expandedKeys = useMemo(() => collectIds(menus), [menus])
  const parentOptions = useMemo(() => toTreeData(menus, editing?.id), [menus, editing])

  const openCreate = (parentId?: number, type: number = 2) => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ parent_id: parentId ?? null, type, visible: 1, is_external: 0, sort_order: 1, status: 1 })
    setModalOpen(true)
  }

  const openEdit = (record: MenuItem2) => {
    setEditing(record)
    form.setFieldsValue({
      parent_id: record.parent_id,
      name: record.name,
      type: record.type,
      path: record.path,
      component: record.component,
      icon: record.icon,
      permission_code: record.permission_code,
      visible: record.visible ?? 1,
      is_external: record.is_external ?? 0,
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
        await menuApi.update(editing.id, values)
        message.success('编辑成功')
      } else {
        await menuApi.create(values)
        message.success('新增成功')
      }
      setModalOpen(false)
      loadTree()
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (record: MenuItem2) => {
    await menuApi.toggleStatus(record.id)
    message.success(record.status === 1 ? '已停用' : '已启用')
    loadTree()
  }

  const handleRemove = async (record: MenuItem2) => {
    await menuApi.remove(record.id)
    message.success('删除成功')
    loadTree()
  }

  const handleMove = async (id: number, dir: -1 | 1) => {
    const next = moveNode(menus, id, dir)
    setMenus(next)
    try {
      await menuApi.sort(flattenSort(next))
    } catch {
      loadTree()
    }
  }

  const watchType = Form.useWatch('type', form)

  const columns = [
    { title: '菜单名称', dataIndex: 'name', width: 180 },
    {
      title: '类型',
      dataIndex: 'type',
      width: 70,
      render: (t: number) => {
        const m = MENU_TYPE_TEXT[t]
        return m ? <Tag color={m.color}>{m.text}</Tag> : '-'
      },
    },
    { title: '路由路径', dataIndex: 'path', width: 140, render: (v: string) => v || '-' },
    { title: '组件', dataIndex: 'component', width: 180, render: (v: string) => v || '-' },
    { title: '图标', dataIndex: 'icon', width: 110, render: (v: string) => v || '-' },
    {
      title: '权限标识',
      dataIndex: 'permission_code',
      width: 130,
      render: (v: string) => (v ? <Tag>{v}</Tag> : '-'),
    },
    { title: '排序', dataIndex: 'sort_order', width: 60 },
    {
      title: '显隐',
      dataIndex: 'visible',
      width: 60,
      render: (v: number) => (v === 1 ? '显示' : '隐藏'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 70,
      render: (s: number) => (s === 1 ? <Tag color="green">启用</Tag> : <Tag color="red">停用</Tag>),
    },
    {
      title: '操作',
      key: 'action',
      width: 300,
      render: (_: unknown, record: MenuItem2) => (
        <Space size={4}>
          <HasPermission code="menu:create">
            <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => openCreate(record.id)}>
              新增下级
            </Button>
          </HasPermission>
          <HasPermission code="menu:update">
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          </HasPermission>
          <HasPermission code="menu:sort">
            <Button type="link" size="small" icon={<ArrowUpOutlined />} disabled={!canMove(menus, record.id, -1)} onClick={() => handleMove(record.id, -1)} />
            <Button type="link" size="small" icon={<ArrowDownOutlined />} disabled={!canMove(menus, record.id, 1)} onClick={() => handleMove(record.id, 1)} />
          </HasPermission>
          <HasPermission code="menu:toggle">
            <Popconfirm title={record.status === 1 ? '确认停用？' : '确认启用？'} onConfirm={() => handleToggle(record)}>
              <Button type="link" size="small" danger={record.status === 1}>
                {record.status === 1 ? '停用' : '启用'}
              </Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="menu:delete">
            <Popconfirm title="确认删除该菜单？" onConfirm={() => handleRemove(record)}>
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
        <HasPermission code="menu:create">
          <Button type="primary" onClick={() => openCreate()}>新增顶级菜单</Button>
        </HasPermission>
        <HasPermission code="menu:update">
          <Button onClick={() => setPermOpen(true)}>权限字典管理</Button>
        </HasPermission>
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={menus}
        loading={loading}
        pagination={false}
        expandable={{ expandedRowKeys: expandedKeys }}
        scroll={{ x: 1300 }}
      />

      <Modal
        title={editing ? '编辑菜单' : '新增菜单'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={560}
        forceRender
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="菜单名称" rules={[{ required: true, message: '请输入菜单名称' }]}>
            <Input maxLength={64} />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="type" label="节点类型">
              <Select style={{ width: 140 }}>
                <Select.Option value={1}>目录</Select.Option>
                <Select.Option value={2}>页面</Select.Option>
                <Select.Option value={3}>按钮</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="parent_id" label="上级菜单" extra="不选择则为顶级">
              <TreeSelect allowClear style={{ width: 240 }} treeData={parentOptions as never} placeholder="选择上级菜单" />
            </Form.Item>
          </Space>
          {(watchType ?? 2) !== 3 && (
            <>
              <Form.Item
                name="path"
                label="路由路径"
                rules={[{ required: (watchType ?? 2) !== 3, message: '目录与页面必须配置路由路径' }]}
              >
                <Input placeholder="如 /org/users" />
              </Form.Item>
              <Form.Item name="component" label="组件地址">
                <Input placeholder="如 views/org/user/index" />
              </Form.Item>
            </>
          )}
          {(watchType ?? 2) === 3 && (
            <Form.Item
              name="permission_code"
              label="权限标识"
              rules={[{ required: true, message: '功能按钮必须绑定权限标识' }]}
            >
              <Input placeholder="如 user:create" />
            </Form.Item>
          )}
          <Form.Item name="icon" label="图标名称">
            <Input placeholder="如 UserOutlined" />
          </Form.Item>
          <Space size={24} style={{ display: 'flex' }}>
            <Form.Item name="visible" label="是否显示" valuePropName="checked">
              <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
            </Form.Item>
            <Form.Item name="is_external" label="是否外链" valuePropName="checked">
              <Switch checkedChildren="外链" unCheckedChildren="站内" />
            </Form.Item>
            <Form.Item name="sort_order" label="排序序号">
              <InputNumber min={0} max={999} style={{ width: 110 }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      <PermDictModal open={permOpen} onClose={() => setPermOpen(false)} />
    </Card>
  )
}

/** 权限标识字典管理弹窗 */
function PermDictModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const [pform] = Form.useForm<Partial<PermItem>>()
  const [list, setList] = useState<PermItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<PermItem | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await menuApi.permissions({ keyword: keyword || undefined, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  const openForm = (item?: PermItem) => {
    setEditing(item ?? null)
    pform.resetFields()
    if (item) pform.setFieldsValue(item)
    setFormOpen(true)
  }

  const submit = async () => {
    const values = await pform.validateFields()
    setSaving(true)
    try {
      if (editing) {
        await menuApi.updatePerm(editing.id, values)
        message.success('编辑成功')
      } else {
        await menuApi.createPerm(values)
        message.success('新增成功')
      }
      setFormOpen(false)
      load()
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    { title: '权限名称', dataIndex: 'name', width: 120 },
    { title: '权限编码', dataIndex: 'code', width: 150, render: (v: string) => <Tag>{v}</Tag> },
    { title: '所属模块', dataIndex: 'module', width: 110, render: (v: string) => v || '-' },
    { title: '说明', dataIndex: 'description', render: (v: string) => v || '-' },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, item: PermItem) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => openForm(item)}>编辑</Button>
          <Popconfirm title="确认删除该权限标识？" onConfirm={async () => { await menuApi.removePerm(item.id); message.success('删除成功'); load() }}>
            <Button type="link" size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Modal title="权限标识字典" open={open} onCancel={onClose} footer={null} width={720}>
      <Space style={{ marginBottom: 12 }}>
        <Input.Search
          placeholder="名称/编码/模块"
          allowClear
          style={{ width: 200 }}
          onSearch={(v) => { setKeyword(v); setPage(1) }}
        />
        <Button type="primary" onClick={() => openForm()}>新增权限</Button>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={list}
        loading={loading}
        size="small"
        pagination={{
          current: page,
          pageSize,
          total,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps) },
        }}
        scroll={{ x: 620 }}
      />
      <Modal
        title={editing ? '编辑权限标识' : '新增权限标识'}
        open={formOpen}
        onOk={submit}
        onCancel={() => setFormOpen(false)}
        confirmLoading={saving}
        width={460}
        forceRender
      >
        <Form form={pform} layout="vertical" preserve={false}>
          <Form.Item name="name" label="权限名称" rules={[{ required: true, message: '请输入权限名称' }]}>
            <Input maxLength={64} />
          </Form.Item>
          <Form.Item name="code" label="权限编码" rules={[{ required: true, message: '请输入权限编码' }]}>
            <Input placeholder="如 user:create" maxLength={64} disabled={!!editing} />
          </Form.Item>
          <Form.Item name="module" label="所属模块">
            <Input placeholder="如 用户" maxLength={64} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  )
}
