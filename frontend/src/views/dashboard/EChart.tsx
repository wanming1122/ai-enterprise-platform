import * as echarts from 'echarts'
import { useEffect, useRef } from 'react'

/** 轻量 echarts 封装：初始化/响应式 resize/option 更新/卸载销毁 */
export default function EChart({
  option,
  height = 320,
}: {
  option: echarts.EChartsCoreOption
  height?: number
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    chartRef.current = chart
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, true)
  }, [option])

  return <div ref={ref} style={{ width: '100%', height }} />
}
