import { post } from './request'

export interface RecoveryCodeResult {
  /** email 渠道时为 null（验证码只进邮箱）；demo 渠道直接回显 */
  code: string | null
  expires_in_minutes: number
  /** email=真实邮件下发；demo=未配置SMTP时的演示回显 */
  channel: 'email' | 'demo'
  /** email 渠道返回脱敏邮箱，如 ab***@qq.com */
  email: string | null
}

/** 找回密码（公开接口）：验证码生成 + 重置 */
export const recoveryApi = {
  sendCode: (username: string) =>
    post<RecoveryCodeResult>('/auth/password-recovery/send-code', { username }),
  reset: (data: { username: string; code: string; new_password: string }) =>
    post<null>('/auth/password-recovery/reset', data),
}
