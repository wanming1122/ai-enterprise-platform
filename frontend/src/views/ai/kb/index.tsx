import {
  App,
  Button,
  Card,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Pagination,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd'
import type { UploadFile } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import HasPermission from '@/components/HasPermission'
import { useUserStore } from '@/stores/user'
import { kbApi, type KBBase, type KBChunkItem, type KBFileItem } from '@/api/kb'

/** 解析状态 → 标签（0待解析 1解析中 2已入库 3失败） */
const PARSE_TAG: Record<number, { text: string; color: string }> = {
  0: { text: '待解析', color: 'default' },
  1: { text: '解析中', color: 'processing' },
  2: { text: '已入库', color: 'success' },
  3: { text: '失败', color: 'error' },
}

const isPending = (s: number) => s === 0 || s === 1

const fmtTime = (v: string | null | undefined) => (v ? v.slice(0, 19).replace('T', ' ') : '-')

const fmtSize = (n: number) =>
  n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`

export default function KBManage() {
  const { message, modal } = App.useApp()
  const permissions = useUserStore((s) => s.permissions)
  /** 内容预览为只读入口：需 file:list（与「文件管理」「切片预览」一致，无权限不可点开） */
  const canPreview = permissions.includes('file:list')
  const [filterForm] = Form.useForm<{ keyword?: string }>()
  const [kbForm] = Form.useForm<{
    name: string
    description?: string
    chunk_size: number
    chunk_overlap: number
  }>()

  // ---------- 知识库列表 ----------
  const [keyword, setKeyword] = useState<string | undefined>()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [list, setList] = useState<KBBase[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // ---------- 新建/编辑弹窗 ----------
  const [kbOpen, setKbOpen] = useState(false)
  const [editing, setEditing] = useState<KBBase | null>(null)
  const [saving, setSaving] = useState(false)

  // ---------- 文件抽屉 ----------
  const [filesOpen, setFilesOpen] = useState(false)
  const [currentKb, setCurrentKb] = useState<KBBase | null>(null)
  const [files, setFiles] = useState<KBFileItem[]>([])
  const [filesTotal, setFilesTotal] = useState(0)
  const [filesLoading, setFilesLoading] = useState(false)
  const [filesPage, setFilesPage] = useState(1)
  const [filesPageSize, setFilesPageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<number | undefined>()
  const [uploading, setUploading] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  /** 手动刷新与轮询共用的自增信号：变更后触发文件列表重载 */
  const [filesTick, setFilesTick] = useState(0)

  // ---------- 内容预览弹窗（阅读器式：左文件、右切片全文） ----------
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewKb, setPreviewKb] = useState<KBBase | null>(null)
  const [previewFiles, setPreviewFiles] = useState<KBFileItem[]>([])
  const [previewFilesLoading, setPreviewFilesLoading] = useState(false)
  const [previewFile, setPreviewFile] = useState<KBFileItem | null>(null)
  const [previewChunks, setPreviewChunks] = useState<KBChunkItem[]>([])
  const [previewChunksTotal, setPreviewChunksTotal] = useState(0)
  const [previewChunksLoading, setPreviewChunksLoading] = useState(false)
  const [previewChunksPage, setPreviewChunksPage] = useState(1)
  const [previewKeyword, setPreviewKeyword] = useState<string | undefined>()

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await kbApi.list({ keyword, page, page_size: pageSize })
      setList(res.list)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    loadList()
  }, [loadList])

  const loadFiles = useCallback(async () => {
    if (!currentKb) return
    setFilesLoading(true)
    try {
      const res = await kbApi.files(currentKb.id, {
        parse_status: statusFilter,
        page: filesPage,
        page_size: filesPageSize,
      })
      setFiles(res.list)
      setFilesTotal(res.total)
    } finally {
      setFilesLoading(false)
    }
  }, [currentKb, statusFilter, filesPage, filesPageSize])

  useEffect(() => {
    if (filesOpen) loadFiles()
  }, [filesOpen, loadFiles, filesTick])

  const hasPending = files.some((f) => isPending(f.parse_status))

  // 文件解析为异步任务：抽屉打开且存在待解析/解析中文件时，每 2 秒轮询直至到终态
  useEffect(() => {
    if (!filesOpen || !hasPending) return
    const timer = setTimeout(() => setFilesTick((n) => n + 1), 2000)
    return () => clearTimeout(timer)
  }, [filesOpen, hasPending, filesTick])

  const handleSearch = (values: { keyword?: string }) => {
    setKeyword(values.keyword?.trim() || undefined)
    setPage(1)
  }

  const openKbModal = (record?: KBBase) => {
    setEditing(record ?? null)
    if (record) {
      kbForm.setFieldsValue({
        name: record.name,
        description: record.description ?? undefined,
        chunk_size: record.chunk_size,
        chunk_overlap: record.chunk_overlap,
      })
    } else {
      kbForm.setFieldsValue({ name: undefined, description: undefined, chunk_size: 500, chunk_overlap: 80 })
    }
    setKbOpen(true)
  }

  const handleSaveKb = async () => {
    const values = await kbForm.validateFields()
    setSaving(true)
    try {
      if (editing) {
        const res = await kbApi.update(editing.id, values)
        if (res.requires_rebuild) {
          message.warning('切片参数已保存；已有文件需点击「重建」重新向量化后才会按新参数生效')
        } else {
          message.success('保存成功')
        }
      } else {
        await kbApi.create(values)
        message.success('创建成功，Embedding 模型与维度已锁定')
      }
      setKbOpen(false)
      loadList()
    } finally {
      setSaving(false)
    }
  }

  const handleRebuild = (record: KBBase) => {
    modal.confirm({
      title: `重建「${record.name}」的向量索引？`,
      content: '将删除并重建 collection，按当前切片全量重新向量化，耗时视切片数量而定。',
      okText: '重建',
      onOk: async () => {
        const res = await kbApi.rebuild(record.id)
        message.success(`重建完成，共重嵌入 ${res.chunks} 个切片`)
        loadList()
      },
    })
  }

  const openFiles = (record: KBBase) => {
    setCurrentKb(record)
    setFilesPage(1)
    setStatusFilter(undefined)
    setUploadFile(null)
    setFilesTick((n) => n + 1)
    setFilesOpen(true)
  }

  const handleUpload = async () => {
    if (!currentKb || !uploadFile) return
    setUploading(true)
    try {
      await kbApi.upload(currentKb.id, uploadFile)
      message.success('上传成功，开始解析')
      setUploadFile(null)
      // 重置筛选与页码，确保能看到新文件的状态流转
      setFilesPage(1)
      setStatusFilter(undefined)
      setFilesTick((n) => n + 1)
      loadList()
    } catch {
      // 上传失败（类型/大小/重复等）已由拦截器统一提示
    } finally {
      setUploading(false)
    }
  }

  const handleReparse = async (record: KBFileItem) => {
    await kbApi.reparseFile(record.id)
    message.success('已加入解析队列')
    setFilesTick((n) => n + 1)
  }

  const handleDeleteFile = async (record: KBFileItem) => {
    await kbApi.removeFile(record.id)
    message.success('文件已删除，检索即刻不可见')
    setFilesTick((n) => n + 1)
    loadList()
  }

  // ---------- 内容预览 ----------
  const loadPreviewChunks = useCallback(async () => {
    if (!previewFile) return
    setPreviewChunksLoading(true)
    try {
      const res = await kbApi.chunks(previewFile.id, {
        keyword: previewKeyword,
        page: previewChunksPage,
        page_size: 20,
      })
      setPreviewChunks(res.list)
      setPreviewChunksTotal(res.total)
    } finally {
      setPreviewChunksLoading(false)
    }
  }, [previewFile, previewKeyword, previewChunksPage])

  useEffect(() => {
    if (previewOpen) loadPreviewChunks()
  }, [previewOpen, loadPreviewChunks])

  const selectPreviewFile = (f: KBFileItem) => {
    if (f.parse_status !== 2) {
      message.info('该文件尚未解析完成，暂无可预览内容')
      return
    }
    setPreviewFile(f)
    setPreviewChunksPage(1)
    setPreviewKeyword(undefined)
  }

  const openPreview = async (record: KBBase) => {
    setPreviewKb(record)
    setPreviewFiles([])
    setPreviewFile(null)
    setPreviewChunks([])
    setPreviewChunksTotal(0)
    setPreviewChunksPage(1)
    setPreviewKeyword(undefined)
    setPreviewOpen(true)
    setPreviewFilesLoading(true)
    try {
      const res = await kbApi.files(record.id, { page: 1, page_size: 100 })
      setPreviewFiles(res.list)
      // 默认选中首个已入库文件，开箱即可读
      setPreviewFile(res.list.find((f) => f.parse_status === 2) ?? null)
    } finally {
      setPreviewFilesLoading(false)
    }
  }

  const kbColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 170,
      render: (v: string) =>
        canPreview ? (
          <Tooltip title="点击查看内容">
            <Typography.Text strong style={{ color: 'var(--ant-color-primary)' }}>{v}</Typography.Text>
          </Tooltip>
        ) : (
          <Typography.Text strong>{v}</Typography.Text>
        ),
    },
    { title: '描述', dataIndex: 'description', ellipsis: true, render: (v: string | null) => v || '-' },
    { title: 'Embedding 模型', dataIndex: 'embedding_model', width: 170 },
    { title: '维度', dataIndex: 'embedding_dimension', width: 70 },
    { title: '切分', key: 'chunk', width: 95, render: (_: unknown, r: KBBase) => `${r.chunk_size}/${r.chunk_overlap}` },
    { title: '文件数', dataIndex: 'file_count', width: 75 },
    { title: '切片数', dataIndex: 'chunk_count', width: 75 },
    { title: '创建时间', dataIndex: 'created_at', width: 150, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 265,
      fixed: 'right' as const,
      render: (_: unknown, record: KBBase) => (
        // 阻止冒泡：操作按钮点击不触发整行「内容预览」
        <div onClick={(e) => e.stopPropagation()}>
          <Space size={0}>
            <Button type="link" size="small" onClick={() => openFiles(record)}>文件管理</Button>
            <HasPermission code="kb:update">
              <Button type="link" size="small" onClick={() => handleRebuild(record)}>重建</Button>
              <Button type="link" size="small" onClick={() => openKbModal(record)}>编辑</Button>
            </HasPermission>
            <HasPermission code="kb:delete">
              <Popconfirm
                title="确认删除该知识库？"
                description="其下全部文件将一并删除，列表不再显示。"
                onConfirm={() => {
                  kbApi.remove(record.id).then(() => {
                    message.success('已删除')
                    loadList()
                  })
                }}
              >
                <Button type="link" size="small" danger>删除</Button>
              </Popconfirm>
            </HasPermission>
          </Space>
        </div>
      ),
    },
  ]

  const fileColumns = [
    { title: '文件名', dataIndex: 'file_name', ellipsis: true },
    { title: '类型', dataIndex: 'file_type', width: 70, render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
    { title: '大小', dataIndex: 'file_size', width: 85, render: fmtSize },
    { title: '切片数', dataIndex: 'chunk_count', width: 75 },
    {
      title: '状态',
      dataIndex: 'parse_status',
      width: 90,
      render: (s: number, record: KBFileItem) => {
        const tag = PARSE_TAG[s] || { text: '未知', color: 'default' }
        const node = <Tag color={tag.color}>{tag.text}</Tag>
        if (s === 3 && record.fail_reason) {
          return <Tooltip title={record.fail_reason}><span>{node}</span></Tooltip>
        }
        return node
      },
    },
    { title: '上传时间', dataIndex: 'created_at', width: 140, render: fmtTime },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: KBFileItem) => (
        <Space size={0}>
          <HasPermission code="file:reparse">
            <Popconfirm
              title="重新解析该文件？"
              description="将清空原切片后重新解析入库。"
              onConfirm={() => handleReparse(record)}
            >
              <Button type="link" size="small" disabled={isPending(record.parse_status)}>重解析</Button>
            </Popconfirm>
          </HasPermission>
          <HasPermission code="file:delete">
            <Popconfirm
              title="确认删除该文件？"
              description="删除后检索不再引用该文件。"
              onConfirm={() => handleDeleteFile(record)}
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
        <Form.Item name="keyword">
          <Input placeholder="按名称搜索" allowClear style={{ width: 220 }} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">查询</Button>
            <Button onClick={() => { filterForm.resetFields(); setKeyword(undefined); setPage(1) }}>重置</Button>
          </Space>
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }}>
        <HasPermission code="kb:create">
          <Button type="primary" onClick={() => openKbModal()}>新建知识库</Button>
        </HasPermission>
      </Space>

      <Table
        rowKey="id"
        columns={kbColumns}
        dataSource={list}
        loading={loading}
        onRow={(record) =>
          canPreview ? { onClick: () => openPreview(record), style: { cursor: 'pointer' } } : {}
        }
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

      {/* 新建/编辑知识库弹窗 */}
      <Modal
        title={editing ? '编辑知识库' : '新建知识库'}
        open={kbOpen}
        onOk={handleSaveKb}
        onCancel={() => setKbOpen(false)}
        confirmLoading={saving}
        width={480}
        forceRender
      >
        <Form form={kbForm} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入知识库名称' }, { max: 64, message: '不超过 64 字' }]}
          >
            <Input placeholder="如：员工手册" maxLength={64} />
          </Form.Item>
          <Form.Item name="description" label="描述" rules={[{ max: 255, message: '不超过 255 字' }]}>
            <Input.TextArea rows={2} placeholder="知识库用途说明（选填）" maxLength={255} />
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="chunk_size" label="切片长度（字符）" style={{ width: 170 }}>
              <InputNumber min={100} precision={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="chunk_overlap"
              label="切片重叠"
              dependencies={['chunk_size']}
              style={{ width: 170 }}
              rules={[
                ({ getFieldValue }) => ({
                  validator: (_, value) =>
                    value == null || value < getFieldValue('chunk_size')
                      ? Promise.resolve()
                      : Promise.reject(new Error('重叠需小于切片长度')),
                }),
              ]}
            >
              <InputNumber min={0} precision={0} style={{ width: '100%' }} />
            </Form.Item>
          </Space>
          <Typography.Text type="secondary">
            {editing
              ? 'Embedding 模型与维度创建后锁定，不可修改；修改切片长度/重叠后需点击「重建」重新向量化，才会对已有文件生效。'
              : '创建时自动探测并锁定 Embedding 模型与维度（模型由后端配置决定）。'}
          </Typography.Text>
        </Form>
      </Modal>

      {/* 文件管理抽屉 */}
      <Drawer
        title={`文件管理：${currentKb?.name ?? ''}`}
        open={filesOpen}
        onClose={() => setFilesOpen(false)}
        width={880}
      >
        {currentKb && (
          <>
            <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
              模型 {currentKb.embedding_model}（{currentKb.embedding_dimension} 维），切分 {currentKb.chunk_size}/
              {currentKb.chunk_overlap}。上传后自动解析入库，解析完成即可问答引用。
            </Typography.Paragraph>

            <HasPermission code="file:upload">
              <Space direction="vertical" style={{ width: '100%', marginBottom: 8 }} size={8}>
                <Upload.Dragger
                  accept=".pdf,.docx,.md,.txt"
                  maxCount={1}
                  fileList={
                    uploadFile
                      ? ([{ uid: '-1', name: uploadFile.name, status: 'done' }] as UploadFile[])
                      : []
                  }
                  beforeUpload={(file) => {
                    setUploadFile(file as File)
                    return false
                  }}
                  onRemove={() => setUploadFile(null)}
                >
                  <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                  <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
                  <p className="ant-upload-hint">支持 pdf / docx / md / txt，单文件不超过 50MB，同库相同内容不可重复上传</p>
                </Upload.Dragger>
                <Button type="primary" loading={uploading} disabled={!uploadFile} onClick={handleUpload}>
                  开始上传解析
                </Button>
              </Space>
            </HasPermission>

            <Space style={{ marginBottom: 12 }}>
              <Select
                placeholder="解析状态"
                allowClear
                style={{ width: 130 }}
                value={statusFilter}
                onChange={(v) => { setStatusFilter(v); setFilesPage(1) }}
                options={Object.entries(PARSE_TAG).map(([k, v]) => ({ value: Number(k), label: v.text }))}
              />
            </Space>

            <Table
              rowKey="id"
              columns={fileColumns}
              dataSource={files}
              loading={filesLoading}
              pagination={{
                current: filesPage,
                pageSize: filesPageSize,
                total: filesTotal,
                showSizeChanger: true,
                showTotal: (t) => `共 ${t} 条`,
                onChange: (p, ps) => {
                  setFilesPage(p)
                  setFilesPageSize(ps)
                },
              }}
            />
          </>
        )}
      </Drawer>

      {/* 内容预览弹窗（阅读器式：左文件列表、右切片全文） */}
      <Modal
        title={`内容预览：${previewKb?.name ?? ''}`}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width={1040}
        styles={{ body: { paddingTop: 8 } }}
      >
        <div style={{ display: 'flex', gap: 16, height: 560 }}>
          {/* 左：文件列表 */}
          <div
            style={{
              width: 250,
              flexShrink: 0,
              borderRight: '1px solid var(--ant-color-border-secondary)',
              overflowY: 'auto',
              paddingRight: 8,
            }}
          >
            {previewFilesLoading ? (
              <div style={{ textAlign: 'center', paddingTop: 40 }}>
                <Spin />
              </div>
            ) : previewFiles.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无文件" />
            ) : (
              previewFiles.map((f) => {
                const tag = PARSE_TAG[f.parse_status] || { text: '未知', color: 'default' }
                const active = previewFile?.id === f.id
                return (
                  <div
                    key={f.id}
                    onClick={() => selectPreviewFile(f)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 6,
                      marginBottom: 4,
                      cursor: f.parse_status === 2 ? 'pointer' : 'not-allowed',
                      background: active ? 'var(--ant-color-primary-bg)' : undefined,
                    }}
                  >
                    <Typography.Text ellipsis={{ tooltip: f.file_name }} style={{ display: 'block' }}>
                      {f.file_name}
                    </Typography.Text>
                    <Space size={4} style={{ marginTop: 4 }}>
                      <Tag color={tag.color} style={{ marginInlineEnd: 0 }}>{tag.text}</Tag>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>{f.chunk_count} 片</Typography.Text>
                    </Space>
                  </div>
                )
              })
            )}
          </div>

          {/* 右：切片全文 */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Typography.Text strong ellipsis style={{ flex: 1, minWidth: 0 }}>
                {previewFile ? previewFile.file_name : '请选择左侧文件'}
              </Typography.Text>
              {previewFile && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  共 {previewChunksTotal} 片
                </Typography.Text>
              )}
            </div>
            <Input.Search
              allowClear
              placeholder="按切片内容搜索"
              style={{ marginBottom: 10 }}
              disabled={!previewFile}
              onSearch={(v) => {
                setPreviewKeyword(v.trim() || undefined)
                setPreviewChunksPage(1)
              }}
            />
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
              {!previewFile ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择左侧已入库文件查看切片内容" />
              ) : previewChunksLoading ? (
                <div style={{ textAlign: 'center', paddingTop: 40 }}>
                  <Spin />
                </div>
              ) : previewChunks.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无切片" />
              ) : (
                previewChunks.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      border: '1px solid var(--ant-color-border-secondary)',
                      borderRadius: 6,
                      padding: '10px 12px',
                      marginBottom: 10,
                    }}
                  >
                    <Space size={4} wrap style={{ marginBottom: 6 }}>
                      <Tag style={{ marginInlineEnd: 0 }}>#{c.chunk_index}</Tag>
                      {c.title_path && <Tag color="blue" style={{ marginInlineEnd: 0 }}>{c.title_path}</Tag>}
                      {c.page != null && <Tag style={{ marginInlineEnd: 0 }}>第{c.page}页</Tag>}
                      <Tag style={{ marginInlineEnd: 0 }}>
                        {c.chunk_type === 'text' ? '文本' : c.chunk_type === 'table' ? '表格' : '图片描述'}
                      </Tag>
                    </Space>
                    <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                      {c.content}
                    </Typography.Paragraph>
                  </div>
                ))
              )}
            </div>
            {previewFile && previewChunksTotal > 20 && (
              <div style={{ textAlign: 'right', marginTop: 8 }}>
                <Pagination
                  size="small"
                  current={previewChunksPage}
                  pageSize={20}
                  total={previewChunksTotal}
                  showSizeChanger={false}
                  onChange={(p) => setPreviewChunksPage(p)}
                />
              </div>
            )}
          </div>
        </div>
      </Modal>
    </Card>
  )
}
