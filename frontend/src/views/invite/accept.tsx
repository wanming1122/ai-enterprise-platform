import { Alert, Button, Card, Form, Input, Result, Spin, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { invitationApi } from '@/api/invitation'

interface InviteInfo {
  name: string
  department_name: string | null
  role_name: string | null
  post: string | null
  status: number
  status_label: string
  expires_at: string | null
}

/** 公开页面：通过入职邀请链接注册账号（无需登录） */
export default function InviteAccept() {
  const { token = '' } = useParams()
  const navigate = useNavigate()
  const [info, setInfo] = useState<InviteInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [form] = Form.useForm<{ username: string; password: string }>()

  useEffect(() => {
    if (!token) return
    invitationApi
      .publicInfo(token)
      .then(setInfo)
      .catch((e) => setError((e as Error).message || '邀请链接无效'))
      .finally(() => setLoading(false))
  }, [token])

  const acceptable = info?.status === 2

  const handleAccept = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const res = await invitationApi.publicAccept(token, values)
      setDone(res.real_name || res.username)
    } catch {
      // 已由拦截器提示
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin tip="正在校验邀请链接..." />
      </div>
    )
  }

  if (error || !info) {
    return (
      <Result
        status="warning"
        title="邀请链接无效"
        subTitle={error || '请联系邀请人重新发送'}
        extra={<Button type="primary" onClick={() => navigate('/login')}>返回登录</Button>}
        style={{ paddingTop: 80 }}
      />
    )
  }

  if (done) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #1677ff 0%, #52c41a 100%)' }}>
        <Card style={{ width: 420 }}>
          <Result
            status="success"
            title={`欢迎入职，${done}！`}
            subTitle="账号已创建并绑定预设部门与角色，点击下方按钮前往登录。"
            extra={<Button type="primary" onClick={() => navigate('/login')}>前往登录</Button>}
          />
        </Card>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #1677ff 0%, #52c41a 100%)' }}>
      <Card style={{ width: 440, boxShadow: '0 4px 16px rgba(0,0,0,0.12)' }}>
        <Typography.Title level={4} style={{ textAlign: 'center', marginTop: 0 }}>
          入职邀请
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>
          {info.name} · {info.department_name || '未指定部门'} · {info.role_name || '未指定角色'}
          {info.post ? ` · ${info.post}` : ''}
        </Typography.Paragraph>

        {!acceptable && (
          <Alert
            type={info.status === 3 ? 'success' : 'warning'}
            showIcon
            message={`该邀请当前状态：${info.status_label}`}
            description={info.status === 3 ? '该邀请已完成注册。' : '邀请不可用，请联系邀请人重发。'}
            style={{ marginBottom: 12 }}
          />
        )}

        {acceptable && (
          <>
            <Typography.Paragraph type="secondary" style={{ fontSize: 13 }}>
              请设置你的登录账号与密码，提交后账号将自动绑定上方部门与角色。
            </Typography.Paragraph>
            <Form form={form} layout="vertical" onFinish={handleAccept}>
              <Form.Item name="username" rules={[{ required: true, message: '请输入登录账号' }, { pattern: /^[a-zA-Z0-9_]{3,64}$/, message: '3-64位字母/数字/下划线' }]}>
                <Input placeholder="登录账号" maxLength={64} />
              </Form.Item>
              <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '至少6位' }]}>
                <Input.Password placeholder="设置密码（至少6位）" autoComplete="new-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={submitting}>
                完成注册入职
              </Button>
            </Form>
          </>
        )}
      </Card>
    </div>
  )
}
