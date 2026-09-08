/**
 * 页面 loader 注册表（路由级代码分包的单一事实来源）。
 *
 * 后端菜单下发的 component 串（如 `views/org/user/index`）→ 模块懒加载 loader，
 * 渲染（viewMap）与预加载（preloadComponent/preloadPages）共用同一份映射，避免双份维护。
 * import() 幂等且自带模块缓存，配合 inflight 缓存可保证 StrictMode 双调用与重复预载零副作用。
 */
import { lazy, type ComponentType } from 'react'

/** 页面模块统一形状（所有路由页面均为无 props 的默认导出组件） */
type PageModule = { default: ComponentType }

/** 页面清单：key 与数据库 sys_menu.component 列、现有 router 的 lazy import 一一对应 */
const pageEntries: ReadonlyArray<readonly [string, () => Promise<PageModule>]> = [
  ['views/dashboard/index', () => import('@/views/dashboard')],
  ['views/org/user/index', () => import('@/views/org/user')],
  ['views/org/department/index', () => import('@/views/org/department')],
  ['views/org/position/index', () => import('@/views/org/position')],
  ['views/org/role/index', () => import('@/views/org/role')],
  ['views/org/menu/index', () => import('@/views/org/menu')],
  ['views/org/approval/index', () => import('@/views/org/approval')],
  ['views/org/invitation/index', () => import('@/views/org/invitation')],
  ['views/attendance/record/index', () => import('@/views/attendance/record')],
  ['views/attendance/rule/index', () => import('@/views/attendance/rule')],
  ['views/salary/index', () => import('@/views/salary')],
  ['views/profile/info/index', () => import('@/views/profile/info')],
  ['views/profile/salary/index', () => import('@/views/profile/salary')],
  ['views/profile/attendance/index', () => import('@/views/profile/attendance')],
  ['views/ai/kb/index', () => import('@/views/ai/kb')],
  ['views/ai/kb/chat/index', () => import('@/views/ai/kb/chat')],
  ['views/ai/model/index', () => import('@/views/ai/model')],
  ['views/ai/nl2sql/index', () => import('@/views/ai/nl2sql')],
  ['views/ai/nl2sql/product/index', () => import('@/views/ai/nl2sql/product')],
  ['views/ai/nl2sql/history/index', () => import('@/views/ai/nl2sql/history')],
  ['views/ai/chat/index', () => import('@/views/ai/chat')],
  ['views/log/index', () => import('@/views/log')],
  ['views/settings/config/index', () => import('@/views/settings/config')],
  ['views/settings/dict/index', () => import('@/views/settings/dict')],
]

/** component 串 → 原始 loader（供预加载按 key 命中，Map 常数级查找） */
const loadersByKey = new Map(pageEntries)

/** component 串 → 懒加载组件（供路由渲染），key 与后端菜单 component 串一致 */
export const viewMap: Record<string, ComponentType> = {}
for (const [key, loader] of loadersByKey) {
  viewMap[key] = lazy(loader)
}

/** 进行中的预载任务（key → Promise），避免 StrictMode/重复预载重复 import */
const inflight = new Map<string, Promise<unknown>>()

/**
 * 单页预载：提前触发某页面 chunk 下载但不渲染。
 * 未注册/已预载的 component 静默忽略，返回 boolean 表示是否真正发起预载。
 */
export function preloadComponent(component?: string): boolean {
  if (!component) return false
  if (inflight.has(component)) return false
  const loader = loadersByKey.get(component)
  if (!loader) return false
  inflight.set(component, loader().catch(() => undefined))
  return true
}

type IdleTask = () => void

/** 低优先级调度：优先 requestIdleCallback，不可用时降级为延时 setTimeout */
function scheduleIdle(task: IdleTask): void {
  if (typeof window === 'undefined') return
  const idle =
    typeof window.requestIdleCallback === 'function' ? window.requestIdleCallback : null
  if (idle) {
    idle(() => task(), { timeout: 2000 })
    return
  }
  window.setTimeout(task, 300)
}

/**
 * 批量预载：仅下载尚未缓存的目标页 chunk。
 * 分批执行（每批 2 个、批间让出主线程），避免开发模式一次性即时编译全部页面造成卡顿、
 * 或生产模式低优先级下载集中抢占带宽。
 */
export function preloadPages(components: string[]): void {
  const pending = [...new Set(components)].filter(
    (c) => Boolean(c) && loadersByKey.has(c) && !inflight.has(c),
  )
  if (!pending.length) return

  const BATCH_SIZE = 2
  let index = 0
  const run = (): void => {
    const batch = pending.slice(index, index + BATCH_SIZE)
    index += BATCH_SIZE
    batch.forEach(preloadComponent)
    if (index < pending.length) {
      scheduleIdle(run)
    }
  }
  scheduleIdle(run)
}
