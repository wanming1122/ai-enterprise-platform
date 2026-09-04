import { Card, Typography } from 'antd'
import { useUserStore } from '@/stores/user'

/** M0 占位首页，M5 起替换为工作台数据看板 */
export default function Dashboard() {
  const { userInfo } = useUserStore()
  const userName = userInfo?.nickname || userInfo?.username || '访客'

  return (
    <Card>
      <Typography.Title level={4}>欢迎使用企业管理系统</Typography.Title>
      <Typography.Paragraph>
        {userName}，当前为 M0 前端骨架占位首页。登录、动态菜单与数据看板将随里程碑逐步接入。
      </Typography.Paragraph>
    </Card>
  )
}