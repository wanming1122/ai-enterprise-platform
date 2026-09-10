/**
 * 中国大陆手机号校验工具：清洗分隔符 → 格式校验 → 结构化结果。
 *
 * 规则：清洗后须为 11 位纯数字（仅 ASCII 数字），且以 1 开头、第二位为 3-9。
 */

export const PHONE_LENGTH = 11

/** 错误码：空串表示校验通过 */
export type PhoneErrorCode = '' | 'empty' | 'illegal_chars' | 'length' | 'prefix'

export interface PhoneCheckResult {
  /** 是否通过校验 */
  valid: boolean
  /** 错误码；通过时为空串 */
  code: PhoneErrorCode
  /** 面向用户的中文提示；通过时为空串 */
  message: string
  /** 清洗分隔符后的结果（失败时也返回，便于排错/回显） */
  normalized: string
}

/** 常见分隔符：各类空白、各类短横线（含全角）、点号 */
const SEPARATOR_RE = /[\s\u00a0\-–—－.．·]/g

const MESSAGES: Record<Exclude<PhoneErrorCode, ''>, string> = {
  empty: '请输入手机号',
  illegal_chars: '手机号只能包含数字（可用空格或短横线分隔）',
  length: `手机号需为 ${PHONE_LENGTH} 位数字`,
  prefix: '手机号号段不合法（需以 1 开头，第二位为 3-9）',
}

/**
 * 去除空格、短横线等常见分隔符（不做合法性判断）。
 * @param raw 原始输入，可为 null/undefined
 * @returns 清洗后的字符串（空输入返回 ""）
 */
export function normalizePhone(raw: unknown): string {
  return String(raw ?? '').replace(SEPARATOR_RE, '').trim()
}

/**
 * 校验中国大陆手机号。
 * 校验顺序：空输入 → 非法字符 → 长度 → 号段（保证提示指向最根本的问题）。
 * @param raw 原始输入，允许携带分隔符
 * @returns PhoneCheckResult
 */
export function checkPhone(raw: unknown): PhoneCheckResult {
  const normalized = normalizePhone(raw)
  const fail = (code: Exclude<PhoneErrorCode, ''>): PhoneCheckResult => ({
    valid: false,
    code,
    message: MESSAGES[code],
    normalized,
  })

  if (!normalized) return fail('empty')
  if (!/^\d+$/.test(normalized)) return fail('illegal_chars')
  if (normalized.length !== PHONE_LENGTH) return fail('length')
  if (!/^1[3-9]/.test(normalized)) return fail('prefix')

  return { valid: true, code: '', message: '', normalized }
}

/** 便捷布尔判断，等价于 checkPhone(raw).valid */
export function isValidPhone(raw: unknown): boolean {
  return checkPhone(raw).valid
}

/**
 * antd Form 校验规则：空值交由 required 规则处理（负责必填提示与星号），
 * 非空时按格式给出对应错误提示。
 *
 * 用法：<Form.Item rules={[{ required: true, whitespace: true, message: '请输入手机号' }, phoneRule()]}>
 */
export function phoneRule() {
  return {
    validator: (_: unknown, value: unknown): Promise<void> => {
      if (value === undefined || value === null || String(value).trim() === '') {
        return Promise.resolve()
      }
      const result = checkPhone(value)
      return result.valid ? Promise.resolve() : Promise.reject(new Error(result.message))
    },
  }
}
