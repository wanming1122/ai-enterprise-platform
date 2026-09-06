import { App as AntdApp, ConfigProvider, theme as antdTheme } from 'antd'
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
  const dark = useUserStore((s) => s.userInfo?.preferences?.theme === 'dark')

  // 应用启动：若本地有令牌则恢复用户/菜单/权限
  useEffect(() => {
    if (!initialized) {
      initSession()
    }
  }, [initialized, initSession])

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        // cssVar 开启后暴露 --ant-* 变量，自定义样式（气泡/代码块等）跟随明暗切换
        cssVar: true,
        algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
      }}
    >
      <AntdApp>
        <AppRoutes />
      </AntdApp>
    </ConfigProvider>
  )
}
