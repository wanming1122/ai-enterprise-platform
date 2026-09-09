import { Button, Card, Col, Row, Statistic, Typography } from 'antd'
import {
  ApartmentOutlined,
  IdcardOutlined,
  PayCircleOutlined,
  ReloadOutlined,
  TeamOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { dashboardApi, type DashboardSummary } from '@/api/dashboard'
import { useUserStore } from '@/stores/user'
import EChart from './EChart'

const PALETTE = ['#1677ff', '#52c41a', '#faad14', '#fa541c', '#722ed1', '#13c2c2', '#eb2f96', '#2f54eb']

function greeting(): string {
  const h = dayjs().hour()
  if (h < 6) return '夜深了'
  if (h < 9) return '早上好'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

export default function Dashboard() {
  const { userInfo } = useUserStore()
  const userName = userInfo?.nickname || userInfo?.username || '访客'
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setSummary(await dashboardApi.summary())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const deptOption = useMemo(
    () => ({
      color: PALETTE,
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 24, top: 30, bottom: 60 },
      xAxis: {
        type: 'category',
        data: summary?.dept_distribution.map((d) => d.name) ?? [],
        axisLabel: { rotate: 30, interval: 0 },
      },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          name: '在职人数',
          type: 'bar',
          barMaxWidth: 36,
          itemStyle: { color: PALETTE[0], borderRadius: [4, 4, 0, 0] },
          data: summary?.dept_distribution.map((d) => d.value) ?? [],
        },
      ],
    }),
    [summary],
  )

  const statusOption = useMemo(
    () => ({
      color: PALETTE,
      tooltip: { trigger: 'item', formatter: '{b}：{c} 条（{d}%）' },
      legend: { bottom: 0, type: 'scroll' },
      series: [
        {
          name: '本月考勤状态',
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '46%'],
          itemStyle: { borderRadius: 6, borderWidth: 2, borderColor: '#fff' },
          label: { formatter: '{b} {c}' },
          data: summary?.attendance_month_status ?? [],
        },
      ],
    }),
    [summary],
  )

  const trendOption = useMemo(
    () => ({
      color: PALETTE,
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 24, top: 30, bottom: 40 },
      xAxis: { type: 'category', boundaryGap: false, data: summary?.attendance_trend.map((t) => t.month) ?? [] },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          name: '考勤异常',
          type: 'line',
          smooth: true,
          symbolSize: 7,
          itemStyle: { color: PALETTE[3] },
          areaStyle: { color: 'rgba(250, 84, 28, 0.12)' },
          data: summary?.attendance_trend.map((t) => t.value) ?? [],
        },
      ],
    }),
    [summary],
  )

  const cards = summary
    ? [
        { title: '在职人数', value: summary.user_count, icon: <TeamOutlined style={{ color: PALETTE[0] }} /> },
        { title: '部门数', value: summary.dept_count, icon: <ApartmentOutlined style={{ color: PALETTE[5] }} /> },
        { title: '职位数', value: summary.position_count, icon: <IdcardOutlined style={{ color: PALETTE[4] }} /> },
        {
          title: '本月考勤异常',
          value: summary.month_abnormal_count,
          icon: <WarningOutlined style={{ color: PALETTE[3] }} />,
        },
      ]
    : []

  return (
    /* overflowX:hidden 裁掉 antd Row 的负 margin（gutter=16 时左右各 -8px），避免出现横向滚动条 */
    <div style={{ overflowX: 'hidden' }}>
      {/* 欢迎行 */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {greeting()}，{userName}
            </Typography.Title>
            <Typography.Text type="secondary">
              今天是 {dayjs().format('YYYY年MM月DD日 dddd')}，欢迎回到企业管理系统
            </Typography.Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
            刷新
          </Button>
        </div>
      </Card>

      {/* 统计卡片 */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
        {cards.map((c) => (
          <Card key={c.title} style={{ flex: '1 1 200px' }} loading={loading}>
            <Statistic title={c.title} value={c.value} prefix={c.icon} />
          </Card>
        ))}
        <Card style={{ flex: '1 1 240px' }} loading={loading}>
          <Statistic
            title={`工资单（${summary?.payroll_month ?? '暂无'}）`}
            value={summary?.payroll_total ?? 0}
            precision={2}
            prefix={<PayCircleOutlined style={{ color: PALETTE[1] }} />}
            suffix={
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                元 · {summary?.payroll_count ?? 0} 张
              </Typography.Text>
            }
          />
        </Card>
      </div>

      {/* 图表区 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="各部门在职人数" styles={{ body: { paddingTop: 12 } }}>
            <EChart option={deptOption} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="本月考勤状态分布" styles={{ body: { paddingTop: 12 } }}>
            <EChart option={statusOption} />
          </Card>
        </Col>
        <Col span={24}>
          <Card title="近 6 个月考勤异常趋势" styles={{ body: { paddingTop: 12 } }}>
            <EChart option={trendOption} />
          </Card>
        </Col>

        {/* 新增：薪资趋势和人力结构 */}
        <Col xs={24} lg={12}>
          <Card title="近6个月薪资成本趋势" styles={{ body: { paddingTop: 12 } }}>
            <EChart
              option={{
                color: PALETTE,
                tooltip: {
                  trigger: 'axis',
                  formatter: (params: any) => {
                    const [bar, line] = params
                    return `${bar.name}<br/>${bar.marker} 薪资总额: ¥${bar.value.toLocaleString()}<br/>${line?.marker || ''} 发放人数: ${line?.value ?? 0}人`
                  },
                },
                legend: { data: ['薪资总额', '发放人数'], bottom: 0 },
                grid: { left: 60, right: 60, top: 30, bottom: 40 },
                xAxis: {
                  type: 'category',
                  data: summary?.salary_trend.map((t) => t.month) ?? [],
                },
                yAxis: [
                  { type: 'value', name: '金额(元)', position: 'left' },
                  { type: 'value', name: '人数', position: 'right', minInterval: 1, splitLine: { show: false } },
                ],
                series: [
                  {
                    name: '薪资总额',
                    type: 'bar',
                    barMaxWidth: 36,
                    itemStyle: { color: PALETTE[0], borderRadius: [4, 4, 0, 0] },
                    data: summary?.salary_trend.map((t) => t.total) ?? [],
                  },
                  {
                    name: '发放人数',
                    type: 'line',
                    yAxisIndex: 1,
                    smooth: true,
                    symbolSize: 7,
                    itemStyle: { color: PALETTE[1] },
                    data: summary?.salary_trend.map((t) => t.count) ?? [],
                  },
                ],
              }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={`各部门薪资分布（${summary?.payroll_month ?? '暂无'}）`} styles={{ body: { paddingTop: 12 } }}>
            <EChart
              option={{
                color: PALETTE,
                tooltip: {
                  trigger: 'item',
                  formatter: (params: any) => `${params.name}<br/>薪资总额: ¥${params.value.toLocaleString()}<br/>占比: ${params.percent}%`,
                },
                legend: { orient: 'vertical', right: 10, top: 'center', type: 'scroll' },
                series: [
                  {
                    type: 'pie',
                    radius: ['42%', '68%'],
                    center: ['40%', '50%'],
                    itemStyle: { borderRadius: 6, borderWidth: 2, borderColor: '#fff' },
                    label: { show: false },
                    emphasis: {
                      label: { show: true, fontSize: 14, fontWeight: 'bold' },
                    },
                    data: summary?.salary_by_dept ?? [],
                  },
                ],
              }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="人力结构分析" styles={{ body: { paddingTop: 12 } }}>
            <Row gutter={16}>
              <Col span={12}>
                <div style={{ textAlign: 'center', marginBottom: 8, fontWeight: 500 }}>性别分布</div>
                <EChart
                  height={250}
                  option={{
                    color: ['#1677ff', '#eb2f96', '#8c8c8c'],
                    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
                    series: [
                      {
                        type: 'pie',
                        radius: ['40%', '70%'],
                        itemStyle: { borderRadius: 6, borderWidth: 2, borderColor: '#fff' },
                        label: { formatter: '{b}\n{d}%' },
                        data: summary?.headcount_structure.gender_distribution ?? [],
                      },
                    ],
                  }}
                />
              </Col>
              <Col span={12}>
                <div style={{ textAlign: 'center', marginBottom: 8, fontWeight: 500 }}>年龄分布</div>
                <EChart
                  height={250}
                  option={{
                    color: PALETTE,
                    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
                    series: [
                      {
                        type: 'pie',
                        radius: ['40%', '70%'],
                        itemStyle: { borderRadius: 6, borderWidth: 2, borderColor: '#fff' },
                        label: { formatter: '{b}\n{d}%' },
                        data: summary?.headcount_structure.age_distribution ?? [],
                      },
                    ],
                  }}
                />
              </Col>
            </Row>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="职位人数TOP8" styles={{ body: { paddingTop: 12 } }}>
            <EChart
              option={{
                color: PALETTE,
                tooltip: { trigger: 'axis' },
                grid: { left: 80, right: 24, top: 30, bottom: 40 },
                xAxis: { type: 'value', minInterval: 1 },
                yAxis: {
                  type: 'category',
                  data: [...(summary?.position_distribution ?? [])].reverse().map((p) => p.name),
                  axisLabel: { width: 60, overflow: 'truncate' },
                },
                series: [
                  {
                    type: 'bar',
                    barMaxWidth: 24,
                    itemStyle: { color: PALETTE[4], borderRadius: [0, 4, 4, 0] },
                    data: [...(summary?.position_distribution ?? [])].reverse().map((p) => p.value),
                  },
                ],
              }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
