"""认证与权限依赖：Bearer Token 解析、当前用户获取、权限校验、数据范围控制。"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import ACCESS_TYPE, decode_token
from app.db.session import get_db
from app.models.role import SysRole
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
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


def get_data_scope(user: SysUser, db: Session) -> tuple[int, int | None]:
    """获取用户的数据范围权限。

    返回:
        (scope_type, department_id):
        - scope_type: 1仅本人 2本部门 3全部
        - department_id: 仅当scope_type=2时返回用户所属部门ID
    """
    from app.services.menu_service import is_super_admin

    # 超级管理员拥有全部数据范围
    if is_super_admin(db, user.id):
        return 3, None

    # 获取用户所有角色中最大的数据范围
    roles = db.scalars(
        select(SysRole.data_scope)
        .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
        .where(
            SysUserRoleRelation.user_id == user.id,
            SysRole.status == 1,  # 仅启用中的角色
        )
    ).all()

    if not roles:
        # 无角色默认仅本人
        return 1, user.department_id

    # 取最大范围（3全部 > 2本部门 > 1本人）
    max_scope = max(roles)

    if max_scope == 2:
        return 2, user.department_id
    return max_scope, None


def apply_data_scope(query, model, user: SysUser, db: Session, user_field: str = "user_id"):
    """根据数据范围自动过滤查询。

    Args:
        query: SQLAlchemy查询对象
        model: 要查询的模型类（需有user_field字段）
        user: 当前登录用户
        db: 数据库会话
        user_field: 模型中关联用户的字段名，默认为"user_id"

    Returns:
        添加了数据范围过滤条件的查询对象
    """
    scope, dept_id = get_data_scope(user, db)

    if scope == 1:  # 仅本人
        return query.where(getattr(model, user_field) == user.id)
    elif scope == 2 and dept_id:  # 本部门
        # 需要JOIN用户表来过滤部门
        return query.join(SysUser, SysUser.id == getattr(model, user_field)).where(
            SysUser.department_id == dept_id
        )
    # scope == 3: 全部，不过滤
    return query
