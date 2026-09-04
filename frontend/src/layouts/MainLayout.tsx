import { Layout, Menu, Dropdown, Avatar, Space, Typography } from 'antd'
import type { MenuProps } from 'antd'
import {
  ApartmentOutlined,
  DashboardOutlined,
  FileTextOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useState, type ReactNode } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useUserStore } from '@/stores/user'
import type { MenuItem } from '@/types'

const { Sider, Header, Content } = Layout

/** 菜单图标映射：后端存储的图标名 → antd 图标组件 */
const iconMap: Record<string, ReactNode> = {
  DashboardOutlined: <DashboardOutlined />,
  ApartmentOutlined: <ApartmentOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  SettingOutlined: <SettingOutlined />,
  UserOutlined: <UserOutlined />,
}

/** 授权菜单树 → antd Menu items（目录转子菜单） */
function toMenuItems(menus: MenuItem[]): NonNullable<MenuProps['items']> {
  return menus.map((m) => {
    const item = {
      key: m.path ?? String(m.id),
      icon: m.icon ? iconMap[m.icon] : undefined,
      label: m.name,
    }
    if (m.type === 'dir' && m.children?.length) {
      return { ...item, children: toMenuItems(m.children) }
    }
    return item
  })
}

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { userInfo, menus, logout } = useUserStore()

  const handleLogout = async () => {
    await logout()
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
          items={toMenuItems(menus)}
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
