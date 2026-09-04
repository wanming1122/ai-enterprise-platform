"""角色路由：本阶段仅提供下拉选项（完整角色管理在 M1-T5）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.role import SysRole
from app.models.user import SysUser
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/roles", tags=["角色管理"])


@router.get("/options")
def role_options(
    _: SysUser = Depends(require_permissions("user:list")),
    db: Session = Depends(get_db),
):
    """启用角色列表（供用户管理等下拉选择）。"""
    roles = db.scalars(select(SysRole).where(SysRole.status == 1).order_by(SysRole.id)).all()
    return ok([{"id": r.id, "name": r.name, "code": r.code} for r in roles])
