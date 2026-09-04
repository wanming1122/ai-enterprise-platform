import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { useEffect } from 'react'
import AppRoutes from '@/router'
import { useUserStore } from '@/stores/user'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

export default function App() {
  const initialized = useUserStore((s) => s.initialized)
  const initSession = useUserStore((s) => s.initSession)

  // 应用启动：若本地有令牌则恢复用户/菜单/权限
  useEffect(() => {
    if (!initialized) {
      initSession()
    }
  }, [initialized, initSession])

  return (
    <ConfigProvider locale={zhCN}>
      <AppRoutes />
    </ConfigProvider>
  )
}
