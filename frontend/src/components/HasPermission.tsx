import type { ReactNode } from 'react'
import { useUserStore } from '@/stores/user'

/** 权限判断 Hook：当前用户是否具备某权限码 */
export function usePermission() {
  const permissions = useUserStore((s) => s.permissions)
  return (code: string): boolean => permissions.includes(code)
}

/** 权限按钮组件：无对应权限码时不渲染子元素（后端仍会拦截越权请求） */
export default function HasPermission({ code, children }: { code: string; children: ReactNode }) {
  const has = usePermission()
  if (!has(code)) return null
  return <>{children}</>
}
