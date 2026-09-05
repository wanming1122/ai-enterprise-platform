import { useMemo, type ComponentType, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from '@/layouts/MainLayout'
import Login from '@/views/login'
import Dashboard from '@/views/dashboard'
import UserManage from '@/views/org/user'
import DepartmentManage from '@/views/org/department'
import RoleManage from '@/views/org/role'
import MenuManage from '@/views/org/menu'
import PositionManage from '@/views/org/position'
import AttendanceRecord from '@/views/attendance/record'
import AttendanceRule from '@/views/attendance/rule'
import SalaryManage from '@/views/salary'
import ProfileInfo from '@/views/profile/info'
import ProfileSalary from '@/views/profile/salary'
import ProfileAttendance from '@/views/profile/attendance'
import KBManage from '@/views/ai/kb'
import KBChat from '@/views/ai/kb/chat'
import ModelConfig from '@/views/ai/model'
import NL2SQL from '@/views/ai/nl2sql'
import NL2SQLProduct from '@/views/ai/nl2sql/product'
import NL2SQLHistory from '@/views/ai/nl2sql/history'
import AIChat from '@/views/ai/chat'
import LogList from '@/views/log'
import Placeholder from '@/views/placeholder'
import { useUserStore } from '@/stores/user'
import type { MenuItem } from '@/types'

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
}

function renderView(component?: string, name?: string): ReactNode {
  const View = component && viewMap[component]
  if (View) return <View />
  return <Placeholder name={name} />
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
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/" replace /> : <Login />} />
        {/* 登录守卫：未认证访问主布局重定向到登录页 */}
        <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" replace />}>
          <Route index element={<Dashboard />} />
          {dynamicRoutes}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
