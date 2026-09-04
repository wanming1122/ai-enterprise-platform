import { Card, Empty } from 'antd'
import { useLocation } from 'react-router-dom'

/** 通用占位页：动态路由已注册但页面尚未实现的模块统一展示 */
export default function Placeholder({ name }: { name?: string }) {
  const location = useLocation()
  return (
    <Card>
      <Empty description={`${name || location.pathname}：功能开发中，敬请期待`} />
    </Card>
  )
}
