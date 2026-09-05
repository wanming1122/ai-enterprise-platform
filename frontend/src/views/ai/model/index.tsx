import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import {
  aiModelApi,
  MODEL_TYPE_OPTIONS,
  PROVIDER_BASE_URL_HINT,
  PROVIDER_OPTIONS,
  type AIModelItem,
} from '@/api/aiModel'

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

interface ModelFormValues {
  name: string
  model_type: AIModelItem['model_type']
  provider: AIModelItem['provider']
  base_url?: string
  api_key?: string
  model_name: string
  temperature?: number | null
  remark?: string
  is_default: boolean
  status: number
}

export default function ModelConfig() {
  const { message } = App.useApp()
  const [filterForm] = Form.useForm<{ model_type?: string; keyword?: string }>()
  const [form] = Form.useForm<ModelFormValues>()

  const [filters, setFilters] = useState<{ model_type?: string; keyword?: string }>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<AIModelItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AIModelItem | null>(null)
  const [saving, setSaving] = useState(false)
  /** 连通性测试进行中的行 */
  const [testingId, setTestingId] = useState<number | null>(null)
  const watchedType = Form.useWatch('model_type', form)
  const watchedProvider = Form.useWatch('provider', form)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await aiModelApi.list({ ...filters, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleSearch = (values: { model_type?: string; keyword?: string }) => {
    setFilters({ model_type: values.model_type, keyword: values.keyword?.trim() || undefined })
    setPage(1)
  }

  const openModal = (record?: AIModelItem) => {
    setEditing(record ?? null)
    if (record) {
      form.setFieldsValue({
        name: record.name,
        model_type: record.model_type,
        provider: record.provider,
        base_url: record.base_url ?? undefined,
        api_key: undefined,
        model_name: record.model_name,
        temperature: record.temperature ?? undefined,
        remark: record.remark ?? undefined,
        is_default: record.is_default,
        status: record.status === 0 ? 0 : 1,
      })
    } else {
      form.setFieldsValue({
        name: undefined, model_type: 'llm', provider: 'zhipu', base_url: undefined,
        api_key: undefined, model_name: undefined, temperature: 0.1, remark: undefined,
        is_default: false, status: 1,
      })
    }
    setModalOpen(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      const payload = { ...values, api_key: values.api_key || undefined }
      if (editing) {
        await aiModelApi.update(editing.id, payload)
        message.success('保存成功')
      } else {
        await aiModelApi.create(payload)
        message.success('新增成功')
      }
      setModalOpen(false)
      loadList()
    } catch {
      // 校验/请求错误已由表单与拦截器提示
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (record: AIModelItem) => {
    setTestingId(record.id)
    try {
      const res = await aiModelApi.test(record.id)
      message.success(`连通正常（${res.latency_ms}ms），${res.detail}`)
    } catch {
      // 失败原因已由拦截器提示
    } finally {
      setTestingId(null)
    }
  }

  const handleSetDefault = async (record: AIModelItem) => {
    await aiModelApi.setDefault(record.id)
    message.success(`已将「${record.name}」设为${record.model_type_label}默认`)
    loadList()
  }

  const columns = [
    {
      title: '配置名称',
      dataIndex: 'name',
      width: 150,
      render: (v: string, r: AIModelItem) => (
        <Space size={6}>
          <Typography.Text strong>{v}</Typography.Text>
          {r.is_default && <Tag color="gold">默认</Tag>}
        </Space>
      ),
    },
    { title: '类型', dataIndex: 'model_type_label', width: 90, render: (v: string) => <Tag>{v}</Tag> },
    { title: '服务商', dataIndex: 'provider_label', width: 100 },
    { title: '模型名称', dataIndex: 'model_name', width: 150, ellipsis: true },
    {
      title: '接口地址',
      dataIndex: 'base_url',
      ellipsis: true,
      render: (v: string | null) => v || '（提供方默认）',
    },
    {
      title: '温度',
      dataIndex: 'temperature',
      width: 70,
      render: (v: number | null, r: AIModelItem) => (r.model_type === 'llm' && v != null ? v : '-'),
    },
    { title: '密钥', dataIndex: 'api_key_masked', width: 110 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 75,
      render: (s: number) => (
        <Tag color={s === 1 ? 'success' : 'default'}>{s === 1 ? '启用' : '停用'}</Tag>
      ),
    },
    { title: '备注', dataIndex: 'remark', ellipsis: true, render: (v: string | null) => v || '-' },
    { title: '创建时间', dataIndex: 'created_at', width: 140, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 190,
      fixed: 'right' as const,
      render: (_: unknown, record: AIModelItem) => (
        <Space size={0}>
          <HasPermission code="model:test">
            <Button
              type="link"
              size="small"
              style={{ color: '#52c41a' }}
              loading={testingId === record.id}
              onClick={() => handleTest(record)}
            >
              测试
            </Button>
          </HasPermission>
          <HasPermission code="model:update">
            {record.is_default ? (
              <Tooltip title="已是该类型默认">
                <Button type="link" size="small" disabled>设默认</Button>
              </Tooltip>
            ) : (
              <Popconfirm
                title={`设为${record.model_type_label}默认？`}
                description="同类型当前默认将被替换。"
                onConfirm={() => handleSetDefault(record)}
              >
                <Button type="link" size="small" disabled={record.status !== 1}>设默认</Button>
              </Popconfirm>
            )}
            <Button type="link" size="small" onClick={() => openModal(record)}>编辑</Button>
          </HasPermission>
          <HasPermission code="model:delete">
            <Popconfirm
              title="确认删除该模型配置？"
              description="删除后列表不再显示；若为默认配置，相关功能将回退 .env 配置。"
              onConfirm={() => {
                aiModelApi.remove(record.id).then(() => {
                  message.success('已删除')
                  loadList()
                })
              }}
            >
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          </HasPermission>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Form layout="inline" form={filterForm} onFinish={handleSearch} style={{ marginBottom: 16, rowGap: 12 }}>
        <Form.Item name="model_type">
          <Select placeholder="模型类型" allowClear style={{ width: 130 }} options={MODEL_TYPE_OPTIONS} />
        </Form.Item>
        <Form.Item name="keyword">
          <Input placeholder="按配置名称搜索" allowClear style={{ width: 200 }} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setFilters({}); setPage(1) }}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={loadList}>刷新</Button>
          </Space>
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }}>
        <HasPermission code="model:create">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>新增模型</Button>
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
        scroll={{ x: 1250 }}
      />

      {/* 新增/编辑模型配置弹窗 */}
      <Modal
        title={editing ? '编辑模型配置' : '新增模型配置'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        width={520}
        forceRender
        destroyOnHidden
      >
        <Form form={form} layout="horizontal" labelCol={{ span: 5 }} wrapperCol={{ span: 17 }}>
          <Form.Item name="name" label="配置名称" rules={[{ required: true, message: '请输入配置名称' }, { max: 64, message: '不超过 64 字' }]}>
            <Input placeholder="如：智谱基础api" maxLength={64} />
          </Form.Item>
          <Form.Item name="model_type" label="模型类型" rules={[{ required: true, message: '请选择模型类型' }]}>
            <Select options={MODEL_TYPE_OPTIONS} placeholder="生成 / 向量 / 重排" />
          </Form.Item>
          <Form.Item name="provider" label="服务商" rules={[{ required: true, message: '请选择服务商' }]}>
            <Select options={PROVIDER_OPTIONS} placeholder="智谱 / 通义百炼 / OpenAI兼容 / 本地" />
          </Form.Item>
          <Form.Item
            name="base_url"
            label="接口地址"
            extra={watchedProvider ? PROVIDER_BASE_URL_HINT[watchedProvider] : undefined}
          >
            <Input placeholder="https://...（部分服务商可留空）" maxLength={255} />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API Key"
            rules={editing ? [] : [{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder={editing ? '不修改可留空' : '以 Fernet 加密存储，仅显示掩码'} autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="model_name" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="如：mimo-v2.5 / embedding-3" maxLength={64} />
          </Form.Item>
          {watchedType === 'llm' && (
            <Form.Item name="temperature" label="温度">
              <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} placeholder="生成温度，默认 0.1" />
            </Form.Item>
          )}
          <Form.Item name="is_default" label="默认模型" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Radio.Group>
              <Radio value={1}>启用</Radio>
              <Radio value={0}>停用</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} placeholder="用途说明（选填）" maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
