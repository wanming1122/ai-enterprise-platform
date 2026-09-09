import { get } from './request'

export interface DistributionItem {
  name: string
  value: number
}

export interface TrendItem {
  month: string
  value: number
}

export interface SalaryTrendItem {
  month: string
  total: number
  count: number
}

export interface SalaryDeptItem {
  name: string
  value: number
  count: number
}

export interface HeadcountStructure {
  gender_distribution: DistributionItem[]
  age_distribution: DistributionItem[]
}

export interface DashboardSummary {
  user_count: number
  dept_count: number
  position_count: number
  month_abnormal_count: number
  payroll_month: string | null
  payroll_count: number
  payroll_total: number
  dept_distribution: DistributionItem[]
  position_distribution: DistributionItem[]
  attendance_month_status: DistributionItem[]
  attendance_trend: TrendItem[]
  salary_trend: SalaryTrendItem[]
  salary_by_dept: SalaryDeptItem[]
  headcount_structure: HeadcountStructure
}

export const dashboardApi = {
  summary: () => get<DashboardSummary>('/dashboard/summary'),
}
