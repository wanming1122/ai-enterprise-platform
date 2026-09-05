"""职位管理路由：列表/新增/编辑/软删/启停与下拉选项。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.role import SysRole
from app.models.user import SysUser
from app.schemas.position import PositionCreate, PositionUpdate
from app.services import position_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/positions", tags=["职位管理"])


@router.get("/options")
def position_options(
    _: SysUser = Depends(require_permissions("user:list")),
    db: Session = Depends(get_db),
):
    """启用职位列表（供用户管理等下拉选择）。"""
    return ok(position_service.list_options(db))


@router.get("/role-options")
def role_options(
    _: SysUser = Depends(require_permissions("position:list")),
    db: Session = Depends(get_db),
):
    """启用角色列表（供职位绑定角色下拉选择）。"""
    roles = db.scalars(select(SysRole).where(SysRole.status == 1).order_by(SysRole.id)).all()
    return ok([{"id": r.id, "name": r.name, "code": r.code} for r in roles])


@router.get("")
def list_positions(
    keyword: str | None = Query(default=None),
    role_id: int | None = Query(default=None),
    status: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("position:list")),
    db: Session = Depends(get_db),
):
    """职位分页列表。"""
    items, total = position_service.list_positions(
        db, keyword=keyword, role_id=role_id, status=status, page=page, page_size=page_size
    )
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_position(
    data: PositionCreate,
    operator: SysUser = Depends(require_permissions("position:create")),
    db: Session = Depends(get_db),
):
    """新增职位。"""
    return ok(position_service.create_position(db, data, operator), message="新增成功")


@router.put("/{position_id}")
def update_position(
    position_id: int,
    data: PositionUpdate,
    operator: SysUser = Depends(require_permissions("position:update")),
    db: Session = Depends(get_db),
):
    """编辑职位。"""
    return ok(position_service.update_position(db, position_id, data, operator), message="编辑成功")


@router.delete("/{position_id}")
def delete_position(
    position_id: int,
    operator: SysUser = Depends(require_permissions("position:delete")),
    db: Session = Depends(get_db),
):
    """软删除职位（有员工绑定时禁止删除）。"""
    position_service.delete_position(db, position_id, operator)
    return ok(message="删除成功")


@router.put("/{position_id}/status")
def toggle_status(
    position_id: int,
    operator: SysUser = Depends(require_permissions("position:update")),
    db: Session = Depends(get_db),
):
    """启停职位。"""
    return ok(position_service.toggle_status(db, position_id, operator), message="操作成功")
