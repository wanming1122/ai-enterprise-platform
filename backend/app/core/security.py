"""JWT 令牌工具：双 Token 签发/校验、刷新令牌轮换与黑名单。"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"

# 刷新令牌黑名单（进程内）：刷新轮换/退出后旧 jti 作废，服务重启后清空
_refresh_blacklist: set[str] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": _now(),
        "exp": _now() + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return create_token(user_id, ACCESS_TYPE, timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES))


def create_refresh_token(user_id: int) -> str:
    return create_token(user_id, REFRESH_TYPE, timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS))


def decode_token(token: str, expected_type: str) -> dict:
    """校验并解码令牌；无效/过期/类型不符/黑名单刷新令牌均抛 ValueError。"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ValueError("令牌无效或已过期") from exc
    if payload.get("type") != expected_type:
        raise ValueError("令牌类型错误")
    if expected_type == REFRESH_TYPE and payload.get("jti") in _refresh_blacklist:
        raise ValueError("刷新令牌已作废")
    return payload


def blacklist_refresh_jti(jti: str) -> None:
    """将刷新令牌 jti 加入黑名单（轮换/退出时调用）。"""
    _refresh_blacklist.add(jti)
