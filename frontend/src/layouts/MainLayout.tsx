import { Layout, Menu, Dropdown, Avatar, Space, Typography, notification, theme as antdTheme } from 'antd'
import type { MenuProps } from 'antd'
import {
  ApartmentOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useUserStore } from '@/stores/user'
import { preloadComponent, preloadPages } from '@/router/viewLoaders'
import type { MenuItem } from '@/types'

const { Sider, Header, Content } = Layout

/** 菜单图标映射：后端存储的图标名 → antd 图标组件 */
const iconMap: Record<string, ReactNode> = {
  DashboardOutlined: <DashboardOutlined />,
  ApartmentOutlined: <ApartmentOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  SettingOutlined: <SettingOutlined />,
  UserOutlined: <UserOutlined />,
  RobotOutlined: <RobotOutlined />,
  DatabaseOutlined: <DatabaseOutlined />,
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
  const { userInfo, menus, logout } = useUserStore()
  const prefs = userInfo?.preferences
  // 偏好：侧边菜单默认折叠
  const [collapsed, setCollapsed] = useState(prefs?.sidebar_collapsed ?? false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = antdTheme.useToken()

  // 偏好：站内消息提醒（关闭后进入系统不弹欢迎提醒；sessionStorage 防止同会话重复弹）
  useEffect(() => {
    if (prefs?.notify_enabled === false) return
    if (sessionStorage.getItem('welcomed')) return
    sessionStorage.setItem('welcomed', '1')
    notification.open({
      message: `欢迎回来，${userInfo?.nickname || userInfo?.username || ''}`,
      description: '今天是美好的一天，祝工作顺利～',
      placement: 'bottomRight',
      duration: 3,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  /** 授权菜单 → path→component 映射（菜单点击预载用）与全部页面 component（空闲预载用） */
  const pageIndex = useMemo(() => {
    const byPath = new Map<string, string>()
    const components: string[] = []
    const walk = (items: MenuItem[]) => {
      for (const m of items) {
        if (m.type === 'page' && m.component) {
          if (m.path) byPath.set(m.path, m.component)
          components.push(m.component)
        }
        if (m.children) walk(m.children)
      }
    }
    walk(menus)
    return { byPath, components }
  }, [menus])

  // 主布局挂载后：空闲分批预载授权页面 chunk，使首次点击菜单时页面大多已就绪、直接渲染
  useEffect(() => {
    preloadPages(pageIndex.components)
  }, [pageIndex])

  /** 菜单点击：先触发目标页 chunk 预载（兜底空闲预载尚未完成的场景），再跳转 */
  const handleMenuClick = ({ key }: { key: string }) => {
    const component = pageIndex.byPath.get(key)
    if (component) preloadComponent(component)
    navigate(key)
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
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
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
          {/* 局部 Suspense：页面懒加载挂起时仅内容区空白兜底，侧栏/顶栏保持稳定，不再整屏闪现加载圈 */}
          <Suspense fallback={null}>
            <Outlet />
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  )
}
