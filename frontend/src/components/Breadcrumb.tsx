/**
 * 面包屑导航组件。
 * 基于当前路由路径和授权菜单树动态生成面包屑路径。
 * 支持多级菜单层级，首页始终作为第一级。
 */
import { useMemo } from 'react'
import { Breadcrumb as AntBreadcrumb } from 'antd'
import { HomeOutlined } from '@ant-design/icons'
import { Link, useLocation } from 'react-router-dom'
import { useUserStore } from '@/stores/user'
import type { MenuItem } from '@/types'

/**
 * 在菜单树中查找目标路径的完整层级
 */
function findBreadcrumbPath(
  menus: MenuItem[],
  pathname: string,
  path: MenuItem[] = [],
): MenuItem[] | null {
  for (const menu of menus) {
    const currentPath = [...path, menu]

    // 精确匹配
    if (menu.path === pathname) {
      return currentPath
    }

    // 递归查找子菜单
    if (menu.children?.length) {
      const found = findBreadcrumbPath(menu.children, pathname, currentPath)
      if (found) return found
    }
  }
  return null
}

export default function BreadcrumbNav() {
  const location = useLocation()
  const { menus } = useUserStore()

  const breadcrumbItems = useMemo(() => {
    // 首页不显示面包屑
    if (location.pathname === '/dashboard' || location.pathname === '/') {
      return []
    }

    const path = findBreadcrumbPath(menus, location.pathname)

    // 未找到匹配菜单时只显示首页
    if (!path || path.length === 0) {
      return [{ title: <Link to="/"><HomeOutlined /> 首页</Link> }]
    }

    return [
      { title: <Link to="/"><HomeOutlined /> 首页</Link> },
      ...path.map((item, index) => ({
        title:
          index === path.length - 1 ? (
            <span>{item.name}</span>
          ) : (
            <Link to={item.path || '#'}>{item.name}</Link>
          ),
      })),
    ]
  }, [menus, location.pathname])

  // 首页不显示面包屑
  if (breadcrumbItems.length === 0) {
    return null
  }

  return (
    <AntBreadcrumb
      items={breadcrumbItems}
      style={{ marginBottom: 16 }}
    />
  )
}
