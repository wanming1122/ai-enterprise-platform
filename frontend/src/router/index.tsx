import { useMemo, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from '@/layouts/MainLayout'
import Login from '@/views/login'
import InviteAccept from '@/views/invite/accept'
import Placeholder from '@/views/placeholder'
import { useUserStore } from '@/stores/user'
import { viewMap } from './viewLoaders'
import type { MenuItem } from '@/types'

/**
 * 路由组件。页面按路由懒加载分包（loader 见 ./viewLoaders.ts），首次进入某页时该页
 * chunk 尚未下载，由 MainLayout 内容区的局部 Suspense 兜底（空白），框架保持稳定，
 * 不再出现整屏加载圈；配合 viewLoaders 的空闲预载，绝大多数点击可直接渲染。
 */

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
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/" replace /> : <Login />} />
        {/* 公开页：入职邀请链接注册（无需登录） */}
        <Route path="/invite/:token" element={<InviteAccept />} />
        {/* 登录守卫：未认证访问主布局重定向到登录页；页面懒加载挂起由 MainLayout 内局部 Suspense 兜底 */}
        <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" replace />}>
          <Route index element={<HomeRedirect />} />
          {dynamicRoutes}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
