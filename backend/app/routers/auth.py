"""认证路由：登录 / 刷新令牌轮换 / 退出 / 当前用户信息 / 公开注册申请。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.role import SysRole
from app.models.user import SysUser
from app.schemas.approval import RegisterApplyIn
from app.schemas.auth import LoginIn, LogoutIn, RecoveryResetIn, RecoverySendIn, RefreshIn
from app.services import approval_service, auth_service, password_recovery_service
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


def _client_ip(request: Request) -> str:
    """解析客户端 IP，兼容开发代理的 X-Forwarded-For。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    """账号密码登录：返回双 Token + 用户信息 + 菜单树 + 权限标识。"""
    return ok(auth_service.login(db, data.username, data.password, _client_ip(request)))


@router.post("/refresh")
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    """刷新令牌轮换：旧刷新令牌作废，签发新双 Token。"""
    return ok(auth_service.refresh_tokens(db, data.refresh_token))


@router.post("/logout")
def logout(data: LogoutIn, db: Session = Depends(get_db)):
    """退出登录：刷新令牌加入黑名单。"""
    auth_service.logout(db, data.refresh_token)
    return ok(message="已退出登录")


@router.get("/me")
def me(
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户信息 + 菜单树 + 权限标识（刷新后恢复会话用）。"""
    return ok(auth_service.current_user_payload(db, user))


@router.get("/register-options")
def register_options(db: Session = Depends(get_db)):
    """公开：可申请的注册角色（排除超级管理员）。"""
    roles = db.scalars(
        select(SysRole).where(SysRole.status == 1, SysRole.role_type != 1).order_by(SysRole.id)
    ).all()
    return ok([{"id": r.id, "name": r.name} for r in roles])


@router.post("/register-apply")
def register_apply(data: RegisterApplyIn, request: Request, db: Session = Depends(get_db)):
    """公开：提交注册申请（创建停用账号，等待管理员审批）。"""
    return ok(
        approval_service.register_apply(db, data, _client_ip(request)),
        message="申请已提交，请等待管理员审批",
    )


@router.post("/password-recovery/send-code")
def recovery_send_code(data: RecoverySendIn, request: Request, db: Session = Depends(get_db)):
    """公开：找回密码第一步，生成验证码（限流：账号15分钟3次/IP15分钟10次）。

    SMTP 已配置且账号登记邮箱时真实下发邮件；否则演示回显（data.code 直接返回）。
    """
    result = password_recovery_service.send_code(db, data.username, _client_ip(request))
    if result.get("channel") == "email":
        message = f"验证码已发送至邮箱 {result.get('email')}，10分钟内有效"
    else:
        message = "验证码已生成，10分钟内有效（演示环境直接回显）"
    return ok(result, message=message)


@router.post("/password-recovery/reset")
def recovery_reset(data: RecoveryResetIn, request: Request, db: Session = Depends(get_db)):
    """公开：找回密码第二步，验证码校验通过后重置密码。"""
    password_recovery_service.reset_password(db, data.username, data.code, data.new_password)
    return ok(message="密码已重置，请使用新密码登录")
