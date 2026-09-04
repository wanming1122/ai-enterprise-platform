import { Layout, Menu, Dropdown, Avatar, Space, Typography } from 'antd'
import {
  DashboardOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useUserStore } from '@/stores/user'

const { Sider, Header, Content } = Layout

/** 静态主导航（M1 起由后端菜单树动态生成） */
const navItems = [
  { key: '/', icon: <DashboardOutlined />, label: '工作台' },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { userInfo, logout } = useUserStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const userName = userInfo?.nickname || userInfo?.username || '未登录'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} trigger={null}>
        <div
          style={{
            height: 56,
            margin: 12,
            borderRadius: 8,
            color: '#fff',
            fontSize: collapsed ? 14 : 16,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(255,255,255,0.12)',
          }}
        >
          {collapsed ? '企业' : '企业管理系统'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={navItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,21,41,0.08)',
          }}
        >
          <Space size={12}>
            <Typography.Text
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 16, cursor: 'pointer' }}
            >
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </Typography.Text>
            <Typography.Text type="secondary">企业管理系统</Typography.Text>
          </Space>
          <Dropdown
            menu={{
              items: [
                { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
              ],
            }}
          >
            <Space style={{ cursor: 'pointer' }}>
              <Avatar size="small" icon={<UserOutlined />} />
              <span>{userName}</span>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}