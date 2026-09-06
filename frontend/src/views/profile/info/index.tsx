import {
  App,
  Avatar,
  Button,
  Card,
  DatePicker,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Tag,
  Upload,
} from 'antd'
import { UserOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { useRef, useState } from 'react'
import { profileApi, type ProfileUpdate } from '@/api/profile'
import { useUserStore } from '@/stores/user'
import type { MenuItem } from '@/types'

/** 头像文件压缩为 Data URL（最长边 256px，JPEG 0.8 质量），满足 Data URL 直存方案 */
function compressToDataUrl(file: File, maxSide = 256): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('图片解析失败'))
      img.onload = () => {
        const scale = Math.min(1, maxSide / Math.max(img.width, img.height))
        const canvas = document.createElement('canvas')
        canvas.width = Math.round(img.width * scale)
        canvas.height = Math.round(img.height * scale)
        canvas.getContext('2d')?.drawImage(img, 0, 0, canvas.width, canvas.height)
        resolve(canvas.toDataURL('image/jpeg', 0.8))
      }
      img.src = reader.result as string
    }
    reader.readAsDataURL(file)
  })
}

interface InfoFormValues {
  nickname?: string
  real_name?: string
  gender?: number
  birthday?: Dayjs | null
  email?: string
  phone?: string
  social_account?: string
  avatar?: string
}

export default function ProfileInfo() {
  const { message, modal } = App.useApp()
  const userInfo = useUserStore((s) => s.userInfo)
  const menus = useUserStore((s) => s.menus)
  const updateUserInfo = useUserStore((s) => s.updateUserInfo)
  const [infoForm] = Form.useForm<InfoFormValues>()
  const [pwdForm] = Form.useForm<{ old_password: string; new_password: string; confirm: string }>()
  const [infoOpen, setInfoOpen] = useState(false)
  const [pwdOpen, setPwdOpen] = useState(false)
  const [prefOpen, setPrefOpen] = useState(false)
  const [prefSaving, setPrefSaving] = useState(false)
  const [saving, setSaving] = useState(false)
  const avatarRef = useRef<string | undefined>(undefined)

  if (!userInfo) return null

  const prefs = userInfo.preferences ?? {}

  // 授权菜单树 → 可选的默认首页（仅页面节点）
  const homeOptions: { value: string; label: string }[] = []
  const walkMenus = (items: MenuItem[]) => {
    for (const m of items) {
      if (m.type === 'page' && m.path) homeOptions.push({ value: m.path, label: m.name })
      if (m.children) walkMenus(m.children)
    }
  }
  walkMenus(menus)
  if (!homeOptions.some((o) => o.value === '/dashboard')) {
    homeOptions.unshift({ value: '/dashboard', label: '工作台' })
  }

  const openEdit = () => {
    infoForm.setFieldsValue({
      nickname: userInfo.nickname,
      real_name: userInfo.real_name,
      gender: userInfo.gender ?? 0,
      birthday: userInfo.birthday ? dayjs(userInfo.birthday) : null,
      email: userInfo.email,
      phone: userInfo.phone,
    })
    avatarRef.current = userInfo.avatar
    setInfoOpen(true)
  }

  const handleAvatar = async (file: File) => {
    try {
      avatarRef.current = await compressToDataUrl(file)
      message.success('头像已就绪，点击保存生效')
    } catch {
      message.error('头像处理失败')
    }
    return false // 阻止 antd 默认上传
  }

  const handleSaveInfo = async () => {
    const values = await infoForm.validateFields()
    setSaving(true)
    try {
      const data: ProfileUpdate = {
        nickname: values.nickname,
        real_name: values.real_name,
        gender: values.gender,
        birthday: values.birthday ? values.birthday.format('YYYY-MM-DD') : null,
        email: values.email,
        phone: values.phone,
        social_account: values.social_account,
        avatar: avatarRef.current,
      }
      const user = await profileApi.update(data)
      updateUserInfo({ ...userInfo, ...user })
      message.success('资料已更新')
      setInfoOpen(false)
    } finally {
      setSaving(false)
    }
  }

  const openPrefs = () => setPrefOpen(true)

  const handleSavePrefs = async (values: {
    default_home: string
    sidebar_collapsed: boolean
    notify_enabled: boolean
  }) => {
    setPrefSaving(true)
    try {
      const preferences = await profileApi.updatePreferences(values)
      updateUserInfo({ ...userInfo, preferences })
      message.success('偏好已保存，默认首页与侧边栏折叠下次进入生效')
      setPrefOpen(false)
    } finally {
      setPrefSaving(false)
    }
  }

  const handleChangePwd = async () => {
    const values = await pwdForm.validateFields()
    setSaving(true)
    try {
      await profileApi.changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
      })
      modal.success({
        title: '密码修改成功',
        content: '请使用新密码重新登录',
        onOk: () => {
          setPwdOpen(false)
          pwdForm.resetFields()
          useUserStore.getState().logout()
          window.location.href = '/login'
        },
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card style={{ maxWidth: 720 }}>
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <Space size={24}>
          <Avatar size={80} src={userInfo.avatar || undefined} icon={<UserOutlined />} />
          <div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {userInfo.real_name || userInfo.username}
              {userInfo.status === 0 && <Tag color="red" style={{ marginLeft: 8 }}>已停用</Tag>}
            </div>
            <div style={{ color: '#888' }}>账号：{userInfo.username}</div>
          </div>
        </Space>
        <Descriptions
          column={2}
          bordered
          size="small"
          items={[
            { key: 'nickname', label: '昵称', children: userInfo.nickname || '-' },
            { key: 'real_name', label: '姓名', children: userInfo.real_name || '-' },
            {
              key: 'gender',
              label: '性别',
              children: { 0: '未知', 1: '男', 2: '女' }[userInfo.gender ?? 0] ?? '未知',
            },
            { key: 'birthday', label: '生日', children: userInfo.birthday || '-' },
            { key: 'phone', label: '手机', children: userInfo.phone || '-' },
            { key: 'email', label: '邮箱', children: userInfo.email || '-' },
            { key: 'dept', label: '部门', children: userInfo.dept_name || '-' },
            { key: 'position', label: '职位', children: userInfo.position_name || userInfo.post || '-' },
            {
              key: 'roles',
              label: '角色',
              children: (userInfo.roles ?? []).length
                ? (userInfo.roles ?? []).map((r) => <Tag key={r}>{r}</Tag>)
                : '-',
            },
            {
              key: 'last_login',
              label: '最近登录',
              children: userInfo.last_login_at ? dayjs(userInfo.last_login_at).format('YYYY-MM-DD HH:mm') : '-',
            },
          ]}
        />
        <Space>
          <Button type="primary" onClick={openEdit}>编辑资料</Button>
          <Button onClick={() => { pwdForm.resetFields(); setPwdOpen(true) }}>修改密码</Button>
          <Button onClick={openPrefs}>偏好设置</Button>
        </Space>
      </Space>

      {/* 编辑资料弹窗 */}
      <Modal
        title="编辑个人资料"
        open={infoOpen}
        onOk={handleSaveInfo}
        onCancel={() => setInfoOpen(false)}
        confirmLoading={saving}
        width={520}
        forceRender
      >
        <Form form={infoForm} layout="vertical">
          <Form.Item label="头像">
            <Upload
              accept="image/*"
              showUploadList={false}
              beforeUpload={(file) => handleAvatar(file as File)}
            >
              <Button>选择图片（自动压缩）</Button>
            </Upload>
          </Form.Item>
          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="nickname" label="昵称" style={{ width: 160 }}>
              <Input placeholder="昵称" maxLength={64} />
            </Form.Item>
            <Form.Item name="real_name" label="姓名" style={{ width: 160 }}>
              <Input placeholder="真实姓名" maxLength={64} />
            </Form.Item>
          </Space>
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
          <Form.Item
            name="phone"
            label="手机"
            rules={[{ pattern: /^1\d{10}$/, message: '手机号格式不正确' }]}
          >
            <Input placeholder="手机号" />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
            <Input placeholder="邮箱" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 修改密码弹窗 */}
      <Modal
        title="修改密码"
        open={pwdOpen}
        onOk={handleChangePwd}
        onCancel={() => setPwdOpen(false)}
        confirmLoading={saving}
        width={420}
        forceRender
      >
        <Form form={pwdForm} layout="vertical">
          <Form.Item name="old_password" label="旧密码" rules={[{ required: true, message: '请输入旧密码' }]}>
            <Input.Password placeholder="旧密码" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { pattern: /^(?=.*[A-Za-z])(?=.*\d).{8,}$/, message: '至少8位且包含字母和数字' },
            ]}
          >
            <Input.Password placeholder="至少8位且包含字母和数字" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入新密码" />
          </Form.Item>
        </Form>
      </Modal>
      {/* 偏好设置弹窗 */}
      <Modal
        title="偏好设置"
        open={prefOpen}
        onCancel={() => setPrefOpen(false)}
        footer={null}
        width={440}
        destroyOnHidden
      >
        <Form
          layout="vertical"
          initialValues={{
            default_home: prefs.default_home || '/dashboard',
            sidebar_collapsed: prefs.sidebar_collapsed ?? false,
            notify_enabled: prefs.notify_enabled ?? true,
          }}
          onFinish={handleSavePrefs}
        >
          <Form.Item name="default_home" label="默认首页（登录后落地页）" rules={[{ required: true }]}>
            <Select options={homeOptions} placeholder="选择登录后进入的页面" />
          </Form.Item>
          <Form.Item
            name="sidebar_collapsed"
            label="侧边菜单默认折叠"
            valuePropName="checked"
          >
            <Switch checkedChildren="折叠" unCheckedChildren="展开" />
          </Form.Item>
          <Form.Item
            name="notify_enabled"
            label="站内消息提醒"
            valuePropName="checked"
            extra="关闭后进入系统不再弹出欢迎提醒"
          >
            <Switch checkedChildren="开" unCheckedChildren="关" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={prefSaving}>
            保存偏好
          </Button>
        </Form>
      </Modal>
    </Card>
  )
}
