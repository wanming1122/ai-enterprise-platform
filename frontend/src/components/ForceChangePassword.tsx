/**
 * 强制修改密码页（P3-28）：管理员重置密码后 need_reset_pwd=1，
 * MainLayout 用本组件整体替换业务内容区——改密成功前不允许访问任何业务页面。
 * 改密成功（后端 change_password 清零标记）后更新 store 自动恢复内容区。
 */
import { App, Button, Card, Form, Input, Typography } from 'antd'
import { LockOutlined, SafetyOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { profileApi } from '@/api/profile'
import { useUserStore } from '@/stores/user'

const PWD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/

export default function ForceChangePassword() {
  const { message } = App.useApp()
  const userInfo = useUserStore((s) => s.userInfo)
  const updateUserInfo = useUserStore((s) => s.updateUserInfo)
  const [submitting, setSubmitting] = useState(false)

  const onFinish = async (values: { old_password: string; new_password: string }) => {
    setSubmitting(true)
    try {
      await profileApi.changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
      })
      // 清零标记，MainLayout 随即恢复业务内容区
      if (userInfo) updateUserInfo({ ...userInfo, need_reset_pwd: 0 })
      message.success('密码修改成功，欢迎使用系统')
    } catch {
      // 失败（旧密码错误/强度不足）已由拦截器统一提示
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100%' }}>
      <Card style={{ width: 420 }}>
        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <SafetyOutlined style={{ fontSize: 32, color: 'var(--ant-color-primary)' }} />
          <Typography.Title level={4} style={{ margin: '8px 0 4px' }}>
            请先修改初始密码
          </Typography.Title>
          <Typography.Text type="secondary">
            当前账号使用的是管理员重置的临时密码，修改后方可使用系统各项功能
          </Typography.Text>
        </div>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="old_password"
            label="当前密码（临时密码）"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="临时密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { pattern: PWD_PATTERN, message: '至少8位且包含字母和数字' },
            ]}
          >
            <Input.Password placeholder="至少8位且包含字母和数字" autoComplete="new-password" />
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
            <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>
            修改密码并进入系统
          </Button>
        </Form>
      </Card>
    </div>
  )
}
