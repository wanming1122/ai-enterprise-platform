"""权限标识字典路由：全量管理（查看/新增/编辑/软删）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.services import permission_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/permissions", tags=["权限标识字典"])


@router.get("")
def list_permissions(
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("menu:list")),
    db: Session = Depends(get_db),
):
    """权限标识字典分页列表。"""
    items, total = permission_service.list_permissions(db, keyword=keyword, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_permission(
    data: PermissionCreate,
    operator: SysUser = Depends(require_permissions("menu:update")),
    db: Session = Depends(get_db),
):
    """新增权限标识。"""
    return ok(permission_service.create_permission(db, data, operator), message="新增成功")


@router.put("/{perm_id}")
def update_permission(
    perm_id: int,
    data: PermissionUpdate,
    operator: SysUser = Depends(require_permissions("menu:update")),
    db: Session = Depends(get_db),
):
    """编辑权限标识。"""
    return ok(permission_service.update_permission(db, perm_id, data, operator), message="编辑成功")


@router.delete("/{perm_id}")
def delete_permission(
    perm_id: int,
    operator: SysUser = Depends(require_permissions("menu:update")),
    db: Session = Depends(get_db),
):
    """软删权限标识。"""
    permission_service.delete_permission(db, perm_id, operator)
    return ok(message="删除成功")
