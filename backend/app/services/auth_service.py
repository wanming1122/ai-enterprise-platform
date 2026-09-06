"""认证服务：登录（含账号/IP 限流锁定）、刷新令牌轮换、退出、当前用户聚合。"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    REFRESH_TYPE,
    blacklist_refresh_jti,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.department import SysDepartment
from app.models.position import SysPosition
from app.models.role import SysRole
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
from app.services.menu_service import build_menu_tree, collect_permissions
from app.services.operation_log_service import write_log
from app.services.profile_service import DEFAULT_PREFERENCES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_ACCOUNT_FAIL = 5
MAX_IP_FAIL = 20
LOCK_MINUTES = 15

# IP 维度失败计数与锁定（进程内，服务重启后清空；账号维度持久化于 sys_user）
_ip_fail: dict[str, dict] = {}


def _serialize_user(db: Session, user: SysUser) -> dict:
    """序列化当前用户信息（含部门名、职位与角色编码）。"""
    dept_name = None
    if user.department_id:
        dept = db.get(SysDepartment, user.department_id)
        dept_name = dept.name if dept else None
    position_name = None
    if user.position_id:
        position = db.get(SysPosition, user.position_id)
        position_name = position.name if position and position.status != 2 else None
    roles = db.scalars(
        select(SysRole)
        .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
        .where(SysUserRoleRelation.user_id == user.id, SysRole.status == 1)
    ).all()
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "real_name": user.real_name,
        "avatar": user.avatar,
        "department_id": user.department_id,
        "dept_name": dept_name,
        "position_id": user.position_id,
        "position_name": position_name,
        "post": user.post,
        "phone": user.phone,
        "email": user.email,
        "status": user.status,
        "last_login_at": user.last_login_at,
        "preferences": {**DEFAULT_PREFERENCES, **(user.preferences or {})},
        "roles": [r.code for r in roles],
    }


def _auth_payload(db: Session, user: SysUser) -> dict:
    """登录成功后的聚合返回：双 Token + 用户信息 + 菜单树 + 权限标识。"""
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "user": _serialize_user(db, user),
        "menus": build_menu_tree(db, user.id),
        "permissions": collect_permissions(db, user.id),
    }


def _record_fail(db: Session, user: SysUser | None, username: str, ip: str) -> str | None:
    """记录一次登录失败，累计达到阈值触发账号/IP 锁定；返回刚触发的锁定提示。"""
    now = datetime.now()
    locked_msg = None
    if user is not None:
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_ACCOUNT_FAIL:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            locked_msg = f"连续失败{MAX_ACCOUNT_FAIL}次，账号已锁定{LOCK_MINUTES}分钟"
        db.commit()

    rec = _ip_fail.setdefault(ip, {"count": 0, "lock_until": None})
    rec["count"] += 1
    if rec["count"] >= MAX_IP_FAIL:
        rec["lock_until"] = now + timedelta(minutes=LOCK_MINUTES)
        if locked_msg is None:
            locked_msg = f"IP 连续失败{MAX_IP_FAIL}次，已锁定{LOCK_MINUTES}分钟"

    write_log(
        db,
        user_id=user.id if user else None,
        username=user.username if user else username,
        module="认证",
        action="登录失败",
        ip=ip,
        result=0,
        error_message=locked_msg or "账号或密码错误",
    )
    return locked_msg


def login(db: Session, username: str, password: str, ip: str) -> dict:
    """账号密码登录：限流锁定检查 → 密码校验 → 状态校验 → 更新登录信息 → 写日志。"""
    now = datetime.now()

    # IP 锁定检查
    ip_lock = _ip_fail.get(ip)
    if ip_lock and ip_lock.get("lock_until") and ip_lock["lock_until"] > now:
        remain = max(1, int((ip_lock["lock_until"] - now).total_seconds() // 60))
        raise HTTPException(status_code=403, detail=f"IP 登录过于频繁，请 {remain} 分钟后重试")

    user = db.scalar(select(SysUser).where(SysUser.username == username))

    # 账号锁定检查
    if user is not None and user.locked_until and user.locked_until > now:
        remain = max(1, int((user.locked_until - now).total_seconds() // 60))
        raise HTTPException(status_code=403, detail=f"账号已锁定，请 {remain} 分钟后重试")

    # 密码校验（不区分账号不存在与密码错误，避免账号枚举）
    if user is None or not pwd_context.verify(password, user.password_hash):
        locked_msg = _record_fail(db, user, username, ip)
        raise HTTPException(status_code=401, detail=locked_msg or "账号或密码错误")

    # 账号状态校验
    if user.status == 0:
        write_log(db, user_id=user.id, username=user.username, module="认证",
                  action="登录失败", ip=ip, result=0, error_message="账号已停用")
        raise HTTPException(status_code=403, detail="账号已停用")
    if user.status == 2:
        raise HTTPException(status_code=401, detail="账号不存在")

    # 登录成功：清零失败计数、记录登录信息
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_ip = ip
    user.last_login_at = now
    db.commit()
    _ip_fail.pop(ip, None)

    write_log(db, user_id=user.id, username=user.username, module="认证",
              action="登录", ip=ip, result=1)
    return _auth_payload(db, user)


def refresh_tokens(db: Session, refresh_token: str) -> dict:
    """刷新令牌轮换：校验旧刷新令牌并将其 jti 作废，签发新双 Token。"""
    try:
        payload = decode_token(refresh_token, REFRESH_TYPE)
        user_id = int(payload["sub"])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    blacklist_refresh_jti(payload["jti"])

    user = db.get(SysUser, user_id)
    if user is None or user.status != 1:
        raise HTTPException(status_code=401, detail="账号不可用")
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
    }


def logout(db: Session, refresh_token: str) -> None:
    """退出登录：将刷新令牌 jti 加入黑名单（无效令牌静默忽略）。"""
    try:
        payload = decode_token(refresh_token, REFRESH_TYPE)
        blacklist_refresh_jti(payload["jti"])
    except ValueError:
        pass


def current_user_payload(db: Session, user: SysUser) -> dict:
    """当前用户信息 + 菜单树 + 权限标识（用于刷新后恢复会话）。"""
    return {
        "user": _serialize_user(db, user),
        "menus": build_menu_tree(db, user.id),
        "permissions": collect_permissions(db, user.id),
    }
