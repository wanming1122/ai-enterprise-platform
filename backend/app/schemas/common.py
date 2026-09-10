"""Schema 公共类型与校验器。"""
from typing import Annotated

from pydantic import AfterValidator

from app.utils.phone import check_phone


def _validate_phone(value: str) -> str:
    """校验中国大陆手机号并返回规范化结果（去分隔符后的 11 位纯数字）。

    校验失败抛 ValueError，由全局 RequestValidationError 处理器统一转 422，
    错误信息即中文明细（如"手机号号段不合法（需以 1 开头，第二位为 3-9）"）。
    """
    result = check_phone(value)
    if not result.valid:
        raise ValueError(result.message)
    return result.normalized


# 手机号字段类型：必填 + 自动清洗分隔符 + 号段校验，规范化后入库
# 用法：phone: PhoneStr
PhoneStr = Annotated[str, AfterValidator(_validate_phone)]


__all__ = ["PhoneStr"]
