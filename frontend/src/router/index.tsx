import { createBrowserRouter, Navigate } from 'react-router-dom'
import MainLayout from '@/layouts/MainLayout'
import Login from '@/views/login'
import Dashboard from '@/views/dashboard'

/**
 * 静态路由：登录页 + 主布局（内含占位首页）。
 * M1 起在 MainLayout children 中按后端菜单树动态挂载路由。
 */
export const router = createBrowserRouter(
  [
    { path: '/login', element: <Login /> },
    {
      path: '/',
      element: <MainLayout />,
      children: [
        { index: true, element: <Dashboard /> },
      ],
    },
    { path: '*', element: <Navigate to="/" replace /> },
  ],
  // 对齐 React Router v7 默认行为，消除未来标记警告
  { future: { v7_relativeSplatPath: true } },
)

export default router