import { Suspense, lazy, useMemo, type ComponentType, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from '@/layouts/MainLayout'
import Login from '@/views/login'
import InviteAccept from '@/views/invite/accept'
import Placeholder from '@/views/placeholder'
import { useUserStore } from '@/stores/user'
import type { MenuItem } from '@/types'

/* 页面组件全部惰性加载：按路由自动分包，首屏只加载登录页与框架代码 */
const Dashboard = lazy(() => import('@/views/dashboard'))
const UserManage = lazy(() => import('@/views/org/user'))
const DepartmentManage = lazy(() => import('@/views/org/department'))
const RoleManage = lazy(() => import('@/views/org/role'))
const MenuManage = lazy(() => import('@/views/org/menu'))
const PositionManage = lazy(() => import('@/views/org/position'))
const AttendanceRecord = lazy(() => import('@/views/attendance/record'))
const AttendanceRule = lazy(() => import('@/views/attendance/rule'))
const SalaryManage = lazy(() => import('@/views/salary'))
const ProfileInfo = lazy(() => import('@/views/profile/info'))
const ProfileSalary = lazy(() => import('@/views/profile/salary'))
const ProfileAttendance = lazy(() => import('@/views/profile/attendance'))
const KBManage = lazy(() => import('@/views/ai/kb'))
const KBChat = lazy(() => import('@/views/ai/kb/chat'))
const ModelConfig = lazy(() => import('@/views/ai/model'))
const NL2SQL = lazy(() => import('@/views/ai/nl2sql'))
const NL2SQLProduct = lazy(() => import('@/views/ai/nl2sql/product'))
const NL2SQLHistory = lazy(() => import('@/views/ai/nl2sql/history'))
const AIChat = lazy(() => import('@/views/ai/chat'))
const LogList = lazy(() => import('@/views/log'))
const ApprovalList = lazy(() => import('@/views/org/approval'))
const InvitationList = lazy(() => import('@/views/org/invitation'))
const ConfigList = lazy(() => import('@/views/settings/config'))
const DictList = lazy(() => import('@/views/settings/dict'))

/** 路由切换时的页面加载占位 */
const PageFallback = (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
    <Spin size="large" tip="页面加载中…" />
  </div>
)

/**
 * 菜单组件映射：后端返回的 component 字符串 → 前端页面组件。
 * 未实现的页面统一落到占位页，后续里程碑逐个替换为真实组件。
 */
const viewMap: Record<string, ComponentType> = {
  'views/dashboard/index': Dashboard,
  'views/org/user/index': UserManage,
  'views/org/department/index': DepartmentManage,
  'views/org/position/index': PositionManage,
  'views/attendance/record/index': AttendanceRecord,
  'views/attendance/rule/index': AttendanceRule,
  'views/salary/index': SalaryManage,
  'views/profile/info/index': ProfileInfo,
  'views/profile/salary/index': ProfileSalary,
  'views/profile/attendance/index': ProfileAttendance,
  'views/org/role/index': RoleManage,
  'views/org/menu/index': MenuManage,
  'views/ai/kb/index': KBManage,
  'views/ai/kb/chat/index': KBChat,
  'views/ai/model/index': ModelConfig,
  'views/ai/nl2sql/index': NL2SQL,
  'views/ai/nl2sql/product/index': NL2SQLProduct,
  'views/ai/nl2sql/history/index': NL2SQLHistory,
  'views/ai/chat/index': AIChat,
  'views/log/index': LogList,
  'views/org/approval/index': ApprovalList,
  'views/org/invitation/index': InvitationList,
  'views/settings/config/index': ConfigList,
  'views/settings/dict/index': DictList,
}

function renderView(component?: string, name?: string): ReactNode {
  const View = component && viewMap[component]
  if (View) return <View />
  return <Placeholder name={name} />
}

/** 默认首页跳转：偏好设置的 default_home，仅在授权菜单中存在时生效，避免越权死循环 */
function HomeRedirect() {
  const home = useUserStore((s) => s.userInfo?.preferences?.default_home)
  const menus = useUserStore((s) => s.menus)
  const allowed = new Set<string>()
  const walk = (items: MenuItem[]) => {
    for (const m of items) {
      if (m.type === 'page' && m.path) allowed.add(m.path)
      if (m.children) walk(m.children)
    }
  }
  walk(menus)
  return <Navigate to={home && allowed.has(home) ? home : '/dashboard'} replace />
}

/** 由授权菜单树生成路由表：仅页面节点生成路由，目录只作菜单分组 */
function buildRoutes(menus: MenuItem[]): ReactNode[] {
  return menus.flatMap((menu) => {
    if (menu.type === 'page' && menu.path) {
      return <Route key={menu.id} path={menu.path} element={renderView(menu.component, menu.name)} />
    }
    return menu.children ? buildRoutes(menu.children) : []
  })
}

export default function AppRoutes() {
  const token = useUserStore((s) => s.token)
  const menus = useUserStore((s) => s.menus)
  const initialized = useUserStore((s) => s.initialized)
  const dynamicRoutes = useMemo(() => buildRoutes(menus), [menus])

  // 会话恢复完成前不渲染，避免已登录用户被闪跳到登录页
  if (!initialized) return null

  return (
    <BrowserRouter>
      <Suspense fallback={PageFallback}>
        <Routes>
          <Route path="/login" element={token ? <Navigate to="/" replace /> : <Login />} />
          {/* 公开页：入职邀请链接注册（无需登录） */}
          <Route path="/invite/:token" element={<InviteAccept />} />
          {/* 登录守卫：未认证访问主布局重定向到登录页 */}
          <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" replace />}>
            <Route index element={<HomeRedirect />} />
            {dynamicRoutes}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
