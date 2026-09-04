"""认证与权限依赖：Bearer Token 解析、当前用户获取、权限校验。"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import ACCESS_TYPE, decode_token
from app.db.session import get_db
from app.models.user import SysUser
from app.services.operation_log_service import write_log

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> SysUser:
    """从请求头解析访问令牌并返回当前用户；无效/过期/停用均拒绝。"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未认证")
    try:
        payload = decode_token(credentials.credentials, ACCESS_TYPE)
        user_id = int(payload["sub"])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = db.get(SysUser, user_id)
    if user is None or user.status == 2:
        raise HTTPException(status_code=401, detail="账号不存在")
    if user.status == 0:
        raise HTTPException(status_code=403, detail="账号已停用")
    return user


def require_permissions(*codes: str):
    """权限校验依赖工厂：校验当前用户是否具备任一/全部权限码（超级管理员豁免）。

    用法：``def list_users(_: SysUser = Depends(require_permissions("user:list"))):``
    无权限返回 403 并记录权限拦截审计日志。
    """

    def checker(
        request: Request,
        db: Session = Depends(get_db),
        user: SysUser = Depends(get_current_user),
    ) -> SysUser:
        from app.services.menu_service import collect_permissions, is_super_admin

        if is_super_admin(db, user.id):
            return user
        owned = set(collect_permissions(db, user.id))
        if not set(codes) <= owned:
            write_log(
                db,
                user_id=user.id,
                username=user.username,
                module="权限校验",
                action="权限拦截",
                method=request.method,
                path=request.url.path,
                params={k: v for k, v in request.query_params.items()},
                ip=request.client.host if request.client else "",
                result=0,
                error_message=f"缺少权限: {'、'.join(codes)}",
            )
            raise HTTPException(status_code=403, detail="无权限操作")
        return user

    return checker
