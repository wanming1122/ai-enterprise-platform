"""JWT 令牌工具：双 Token 签发/校验、刷新令牌轮换与宽限作废。"""
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"

# 已作废的刷新令牌（进程内）：jti → 开始拒绝使用的时间戳（秒）。
# 轮换后旧令牌在宽限期内仍可换新，避免多标签页/并发刷新时"后到的请求拿着刚被轮换掉的
# 旧令牌"被判失效，进而触发前端清空令牌、强制退出登录；退出登录 grace=0 立即拒绝。
_refresh_grace: dict[str, float] = {}
# 轮换宽限期：覆盖前端并发请求与多标签页同时刷新的时间窗
ROTATE_GRACE_SECONDS = 30
# 作废记录保留时长：超过刷新令牌自身有效期后，其 JWT 已由 exp 自然过期，无需再记
_RETENTION_SECONDS = settings.JWT_REFRESH_EXPIRE_DAYS * 86400


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
    """校验并解码令牌；无效/过期/类型不符/已作废刷新令牌均抛 ValueError。"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ValueError("令牌无效或已过期") from exc
    if payload.get("type") != expected_type:
        raise ValueError("令牌类型错误")
    if expected_type == REFRESH_TYPE:
        _assert_refresh_usable(payload.get("jti"))
    return payload


def _prune_obsolete(now: float) -> None:
    """回收早已生效作废的记录：超过刷新令牌有效期后其 JWT 已自然过期，无需继续占用内存。"""
    cutoff = now - _RETENTION_SECONDS
    for key in [k for k, v in _refresh_grace.items() if v < cutoff]:
        _refresh_grace.pop(key, None)


def _assert_refresh_usable(jti: str | None) -> None:
    """宽限期内放行已轮换的刷新令牌；超出宽限期后判废。

    注意记录一经写入不再删除：若判废时移除记录，旧令牌下次会因"查不到作废记录"而
    重新通过校验（复活），故只由 _prune_obsolete 在远超有效期后回收。"""
    if not jti:
        return
    effective_at = _refresh_grace.get(jti)
    if effective_at is None:
        return
    if time.time() < effective_at:
        return
    raise ValueError("刷新令牌已作废")


def blacklist_refresh_jti(jti: str, grace_seconds: int = ROTATE_GRACE_SECONDS) -> None:
    """作废刷新令牌：宽限期内仍可重放（并发刷新场景），到期后拒绝使用。
    退出登录应传 grace_seconds=0，使旧令牌立即失效。

    只收紧、不延长：宽限期内被重放时会再次调用本函数，若直接覆盖生效时间，
    旧令牌将被反复续期而永不过期；因此仅在新的生效时间更早时才更新。"""
    now = time.time()
    _prune_obsolete(now)
    effective_at = now + grace_seconds
    existing = _refresh_grace.get(jti)
    if existing is None or effective_at < existing:
        _refresh_grace[jti] = effective_at
