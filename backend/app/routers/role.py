"""角色路由：列表/增删改/启停/菜单授权与下拉选项。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.role import SysRole
from app.models.user import SysUser
from app.schemas.role import RoleAuth, RoleCreate, RoleUpdate
from app.services import role_service
from app.utils.page import page_result
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


@router.get("")
def list_roles(
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("role:list")),
    db: Session = Depends(get_db),
):
    """角色分页列表。"""
    items, total = role_service.list_roles(db, keyword=keyword, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_role(
    data: RoleCreate,
    operator: SysUser = Depends(require_permissions("role:create")),
    db: Session = Depends(get_db),
):
    """新增角色。"""
    return ok(role_service.create_role(db, data, operator), message="新增成功")


@router.get("/{role_id}/menus")
def role_menus(
    role_id: int,
    _: SysUser = Depends(require_permissions("role:list")),
    db: Session = Depends(get_db),
):
    """角色已授权菜单 ID（授权弹窗回显）。"""
    return ok(role_service.get_role_menu_ids(db, role_id))


@router.put("/{role_id}")
def update_role(
    role_id: int,
    data: RoleUpdate,
    operator: SysUser = Depends(require_permissions("role:update")),
    db: Session = Depends(get_db),
):
    """编辑角色。"""
    return ok(role_service.update_role(db, role_id, data, operator), message="编辑成功")


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    operator: SysUser = Depends(require_permissions("role:delete")),
    db: Session = Depends(get_db),
):
    """软删角色（超级管理员角色禁止删除）。"""
    role_service.delete_role(db, role_id, operator)
    return ok(message="删除成功")


@router.put("/{role_id}/status")
def toggle_status(
    role_id: int,
    operator: SysUser = Depends(require_permissions("role:update")),
    db: Session = Depends(get_db),
):
    """启停角色（禁用后该角色用户失去权限）。"""
    return ok(role_service.toggle_status(db, role_id, operator), message="操作成功")


@router.put("/{role_id}/menus")
def authorize_menus(
    role_id: int,
    data: RoleAuth,
    operator: SysUser = Depends(require_permissions("role:authorize")),
    db: Session = Depends(get_db),
):
    """角色菜单批量授权。"""
    role_service.authorize_menus(db, role_id, data.menu_ids, operator)
    return ok(message="授权成功")
