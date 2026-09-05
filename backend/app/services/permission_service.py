"""权限标识字典服务：全量查询与增删改。"""
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.permission import SysPermission
from app.models.user import SysUser
from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.services.operation_log_service import write_log


def serialize_perm(p: SysPermission) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "code": p.code,
        "module": p.module,
        "description": p.description,
        "status": p.status,
    }


def list_permissions(db: Session, *, keyword: str | None = None, page: int = 1, page_size: int = 20):
    q = select(SysPermission).where(SysPermission.status != 2)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(SysPermission.name.like(like), SysPermission.code.like(like), SysPermission.module.like(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    perms = db.scalars(q.order_by(SysPermission.id).offset((page - 1) * page_size).limit(page_size)).all()
    return [serialize_perm(p) for p in perms], total


def _check_code_unique(db: Session, code: str, exclude_id: int | None = None) -> None:
    q = select(SysPermission.id).where(SysPermission.code == code)
    if exclude_id is not None:
        q = q.where(SysPermission.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(status_code=422, detail="权限编码已存在")


def get_perm(db: Session, perm_id: int) -> SysPermission:
    perm = db.get(SysPermission, perm_id)
    if perm is None or perm.status == 2:
        raise HTTPException(status_code=404, detail="权限标识不存在")
    return perm


def create_permission(db: Session, data: PermissionCreate, operator: SysUser) -> dict:
    _check_code_unique(db, data.code)
    perm = SysPermission(name=data.name, code=data.code, module=data.module, description=data.description)
    db.add(perm)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="权限字典",
              action="新增权限", params=data.model_dump(), result=1)
    return serialize_perm(perm)


def update_permission(db: Session, perm_id: int, data: PermissionUpdate, operator: SysUser) -> dict:
    perm = get_perm(db, perm_id)
    updates = data.model_dump(exclude_unset=True)
    if "code" in updates and updates["code"]:
        _check_code_unique(db, updates["code"], exclude_id=perm_id)
    for field, value in updates.items():
        setattr(perm, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="权限字典",
              action="编辑权限", params={"id": perm_id, **updates}, result=1)
    return serialize_perm(perm)


def delete_permission(db: Session, perm_id: int, operator: SysUser) -> None:
    perm = get_perm(db, perm_id)
    perm.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="权限字典",
              action="删除权限", params={"id": perm_id}, result=1)
