"""中国大陆手机号校验工具：清洗分隔符 → 格式校验 → 结构化结果。

校验规则：
- 清洗后须为 11 位纯数字（仅 ASCII 数字，全角数字视为非法字符）；
- 首位必须为 1，第二位必须为 3-9。

纯函数实现（无数据库/网络依赖），便于单元测试与多场景复用。
"""
from dataclasses import dataclass

# ---------- 常量 ----------

PHONE_LENGTH = 11                 # 固定长度
PHONE_PREFIX_PATTERN = r"^1[3-9]"  # 号段：1 开头 + 第二位 3-9

# 错误码
CODE_EMPTY = "empty"                  # 空输入
CODE_ILLEGAL_CHARS = "illegal_chars"  # 含非数字字符
CODE_LENGTH = "length"                # 长度不符
CODE_PREFIX = "prefix"                # 号段不合法

# 各错误码对应的用户提示
MESSAGES = {
    CODE_EMPTY: "请输入手机号",
    CODE_ILLEGAL_CHARS: "手机号只能包含数字（可用空格或短横线分隔）",
    CODE_LENGTH: f"手机号需为 {PHONE_LENGTH} 位数字",
    CODE_PREFIX: "手机号号段不合法（需以 1 开头，第二位为 3-9）",
}

# 常见分隔符：各类空格（半角/全角/不换行）、各类短横线（ASCII/连接号/破折号/全角）、点号
# 仅用于输入清洗，不参与合法性判断
_SEPARATORS = " \t\r\n\u3000\u00a0-–—－.．·"
_TRANSLATE_TABLE = str.maketrans("", "", _SEPARATORS)


@dataclass(frozen=True)
class PhoneCheckResult:
    """手机号校验结果。

    Attributes:
        valid: 是否通过校验。
        code: 错误码；通过时为空串，否则为 empty / illegal_chars / length / prefix。
        message: 面向用户的中文提示；通过时为空串。
        normalized: 清洗分隔符后的字符串（含非法字符或长度不符时也返回，便于回显原文处理结果）。
    """

    valid: bool
    code: str
    message: str
    normalized: str


# ---------- 纯函数 ----------


def normalize_phone(raw: str | None) -> str:
    """去除空格、短横线等常见分隔符，返回清洗后的字符串（不做合法性判断）。

    Args:
        raw: 原始输入，可为 None。

    Returns:
        清洗后的字符串；raw 为 None 时返回空串。
    """
    if raw is None:
        return ""
    return str(raw).translate(_TRANSLATE_TABLE).strip()


def check_phone(raw: str | None) -> PhoneCheckResult:
    """校验中国大陆手机号。

    校验顺序：空输入 → 非法字符 → 长度 → 号段，保证报错指向最根本的问题。

    Args:
        raw: 原始输入，允许携带空格/短横线等分隔符，也可为 None。

    Returns:
        PhoneCheckResult(valid, code, message, normalized)。
    """
    normalized = normalize_phone(raw)

    if not normalized:
        return PhoneCheckResult(False, CODE_EMPTY, MESSAGES[CODE_EMPTY], normalized)
    # isascii 前置：拦截全角数字、阿拉伯-印度数字等 isdigit() 为真的非 ASCII 字符
    if not (normalized.isascii() and normalized.isdigit()):
        return PhoneCheckResult(False, CODE_ILLEGAL_CHARS, MESSAGES[CODE_ILLEGAL_CHARS], normalized)
    if len(normalized) != PHONE_LENGTH:
        return PhoneCheckResult(False, CODE_LENGTH, MESSAGES[CODE_LENGTH], normalized)
    if not (normalized[0] == "1" and normalized[1] in "3456789"):
        return PhoneCheckResult(False, CODE_PREFIX, MESSAGES[CODE_PREFIX], normalized)

    return PhoneCheckResult(True, "", "", normalized)


def is_valid_phone(raw: str | None) -> bool:
    """便捷布尔判断，等价于 check_phone(raw).valid。"""
    return check_phone(raw).valid


__all__ = [
    "PHONE_LENGTH",
    "CODE_EMPTY",
    "CODE_ILLEGAL_CHARS",
    "CODE_LENGTH",
    "CODE_PREFIX",
    "MESSAGES",
    "PhoneCheckResult",
    "normalize_phone",
    "check_phone",
    "is_valid_phone",
]
