import { post } from './request'

export interface RecoveryCodeResult {
  /** 演示环境未接入邮件/短信服务，验证码直接回显 */
  code: string
  expires_in_minutes: number
}

/** 找回密码（公开接口）：验证码生成 + 重置 */
export const recoveryApi = {
  sendCode: (username: string) =>
    post<RecoveryCodeResult>('/auth/password-recovery/send-code', { username }),
  reset: (data: { username: string; code: string; new_password: string }) =>
    post<null>('/auth/password-recovery/reset', data),
}
