"""认证路由：登录 / 刷新令牌轮换 / 退出 / 当前用户信息。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.auth import LoginIn, LogoutIn, RefreshIn
from app.services import auth_service
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
