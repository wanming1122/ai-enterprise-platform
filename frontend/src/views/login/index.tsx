import { Button, Card, Form, Input, Modal, Select, Typography, message } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '@/stores/user'
import { approvalApi, type RegisterRoleOption } from '@/api/approval'

interface RegisterFormValues {
  username: string
  password: string
  real_name: string
  phone?: string
  email?: string
  apply_role_id: number
  apply_comment?: string
}

export default function Login() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { login } = useUserStore()

  const [applyOpen, setApplyOpen] = useState(false)
  const [applyLoading, setApplyLoading] = useState(false)
  const [roleOptions, setRoleOptions] = useState<RegisterRoleOption[]>([])
  const [applyForm] = Form.useForm<RegisterFormValues>()

  useEffect(() => {
    if (applyOpen && !roleOptions.length) {
      approvalApi.registerOptions().then(setRoleOptions).catch(() => setRoleOptions([]))
    }
  }, [applyOpen, roleOptions.length])

  const handleApply = async () => {
    const values = await applyForm.validateFields()
    setApplyLoading(true)
    try {
      await approvalApi.registerApply(values)
      message.success('申请已提交，请等待管理员审批')
      setApplyOpen(false)
      applyForm.resetFields()
    } catch {
      // 已由拦截器提示
    } finally {
      setApplyLoading(false)
    }
  }

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      navigate('/', { replace: true })
    } catch {
      // 错误提示由统一拦截器处理
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1677ff 0%, #52c41a 100%)',
      }}
    >
      <Card style={{ width: 380, boxShadow: '0 4px 16px rgba(0,0,0,0.12)' }}>
        <Typography.Title level={3} style={{ textAlign: 'center', marginTop: 0 }}>
          企业管理系统
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>
          登录后进入工作台（认证接口由 M1 提供）
        </Typography.Paragraph>
        <Form onFinish={onFinish} size="large" autoComplete="off">
          <Form.Item name="username" rules={[{ required: true, message: '请输入账号' }]}>
            <Input prefix={<UserOutlined />} placeholder="账号" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登 录
            </Button>
          </Form.Item>
          <div style={{ textAlign: 'center' }}>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 13, cursor: 'pointer' }}
              onClick={() => setApplyOpen(true)}
            >
              没有账号？申请注册
            </Typography.Text>
          </div>
        </Form>
      </Card>

      {/* 注册申请弹窗：提交后进入管理员审批流程 */}
      <Modal
        title="申请注册账号"
        open={applyOpen}
        onOk={handleApply}
        onCancel={() => setApplyOpen(false)}
        confirmLoading={applyLoading}
        okText="提交申请"
        width={480}
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary">
          提交后将创建停用账号，由管理员审批通过后方可登录。
        </Typography.Paragraph>
        <Form form={applyForm} layout="horizontal" labelCol={{ span: 5 }} wrapperCol={{ span: 17 }} initialValues={{ apply_role_id: undefined }}>
          <Form.Item name="username" label="登录账号" rules={[{ required: true, message: '请输入登录账号' }, { pattern: /^[a-zA-Z0-9_]{3,64}$/, message: '3-64位字母/数字/下划线' }]}>
            <Input placeholder="登录账号" maxLength={64} />
          </Form.Item>
          <Form.Item name="password" label="设置密码" rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '至少6位' }]}>
            <Input.Password placeholder="至少6位" autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="real_name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="真实姓名" maxLength={64} />
          </Form.Item>
          <Form.Item name="phone" label="手机号">
            <Input placeholder="选填" maxLength={20} />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="选填" maxLength={128} />
          </Form.Item>
          <Form.Item name="apply_role_id" label="申请角色" rules={[{ required: true, message: '请选择申请角色' }]}>
            <Select
              placeholder="选择希望的角色"
              options={roleOptions.map((r) => ({ value: r.id, label: r.name }))}
            />
          </Form.Item>
          <Form.Item name="apply_comment" label="申请说明">
            <Input.TextArea rows={2} placeholder="选填，如：入职技术部" maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}