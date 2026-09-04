import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { RouterProvider } from 'react-router-dom'
import { router } from '@/router'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

export default function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <RouterProvider
        router={router}
        future={{ v7_startTransition: true }}
      />
    </ConfigProvider>
  )
}