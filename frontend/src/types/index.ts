// 全局类型定义

/** 统一接口响应格式：code=0 成功，401 未认证，403 无权限，422 参数错误，500 服务器错误 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 分页返回结构 */
export interface PageResult<T> {
  list: T[]
  total: number
  page: number
  page_size: number
}

/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  nickname?: string
  real_name?: string
  avatar?: string
  dept_id?: number | null
  dept_name?: string
  position_id?: number | null
  position_name?: string
  phone?: string
  email?: string
  status?: number
  last_login_at?: string | null
}

/** 菜单节点（后端菜单树驱动动态路由与侧边导航） */
export interface MenuItem {
  id: number
  parent_id: number | null
  name: string
  path?: string
  component?: string
  icon?: string
  type: 'dir' | 'page' | 'button'
  permission?: string | null
  sort?: number
  visible?: number
  children?: MenuItem[]
}

/** 登录返回：双 Token + 用户信息 + 菜单树 + 权限标识 */
export interface LoginResult {
  access_token: string
  refresh_token: string
  user: UserInfo
  menus: MenuItem[]
  permissions: string[]
}