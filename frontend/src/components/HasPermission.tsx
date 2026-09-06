import type { ReactNode } from 'react'
import { useUserStore } from '@/stores/user'

/** 权限按钮组件：无对应权限码时不渲染子元素（后端仍会拦截越权请求） */
export default function HasPermission({ code, children }: { code: string; children: ReactNode }) {
  const permissions = useUserStore((s) => s.permissions)
  if (!permissions.includes(code)) return null
  return <>{children}</>
}
