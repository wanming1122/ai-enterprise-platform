"""角色服务：CRUD、启停、菜单批量授权与授权回显。"""
import re

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.menu import SysMenu
from app.models.role import SysRole
from app.models.role_menu_relation import SysRoleMenuRelation
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
from app.schemas.role import RoleCreate, RoleUpdate
from app.services.operation_log_service import write_log

CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _check_unique(db: Session, field: str, value: str, exclude_id: int | None = None) -> None:
    q = select(SysRole.id).where(getattr(SysRole, field) == value)
    if exclude_id is not None:
        q = q.where(SysRole.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(status_code=422, detail="角色名称或编码已存在")


def serialize_role(db: Session, role: SysRole) -> dict:
    user_count = db.scalar(
        select(func.count())
        .select_from(SysUserRoleRelation)
        .where(SysUserRoleRelation.role_id == role.id)
    ) or 0
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "role_type": role.role_type,
        "description": role.description,
        "status": role.status,
        "user_count": user_count,
        "created_at": role.created_at.isoformat() if role.created_at else None,
    }


def list_roles(db: Session, *, keyword: str | None = None, page: int = 1, page_size: int = 20):
    q = select(SysRole).where(SysRole.status != 2)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(SysRole.name.like(like), SysRole.code.like(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    roles = db.scalars(q.order_by(SysRole.id).offset((page - 1) * page_size).limit(page_size)).all()
    return [serialize_role(db, r) for r in roles], total


def get_role(db: Session, role_id: int) -> SysRole:
    role = db.get(SysRole, role_id)
    if role is None or role.status == 2:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


def create_role(db: Session, data: RoleCreate, operator: SysUser) -> dict:
    if not CODE_PATTERN.match(data.code):
        raise HTTPException(status_code=422, detail="角色编码需以字母开头，仅含字母数字下划线")
    _check_unique(db, "name", data.name)
    _check_unique(db, "code", data.code)
    role = SysRole(name=data.name, code=data.code, role_type=data.role_type, description=data.description)
    db.add(role)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="角色管理",
              action="新增角色", params=data.model_dump(), result=1)
    return serialize_role(db, role)


def update_role(db: Session, role_id: int, data: RoleUpdate, operator: SysUser) -> dict:
    role = get_role(db, role_id)
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"]:
        _check_unique(db, "name", updates["name"], exclude_id=role_id)
    if "code" in updates and updates["code"]:
        if not CODE_PATTERN.match(updates["code"]):
            raise HTTPException(status_code=422, detail="角色编码需以字母开头，仅含字母数字下划线")
        _check_unique(db, "code", updates["code"], exclude_id=role_id)
    for field, value in updates.items():
        setattr(role, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="角色管理",
              action="编辑角色", params={"id": role_id, **updates}, result=1)
    return serialize_role(db, role)


def delete_role(db: Session, role_id: int, operator: SysUser) -> None:
    role = get_role(db, role_id)
    if role.role_type == 1:
        raise HTTPException(status_code=422, detail="超级管理员角色不可删除")
    role.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="角色管理",
              action="删除角色", params={"id": role_id}, result=1)


def toggle_status(db: Session, role_id: int, operator: SysUser) -> dict:
    role = get_role(db, role_id)
    if role.role_type == 1:
        raise HTTPException(status_code=422, detail="超级管理员角色不可停用")
    role.status = 0 if role.status == 1 else 1
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="角色管理",
              action="启停角色", params={"id": role_id, "status": role.status}, result=1)
    return serialize_role(db, role)


def authorize_menus(db: Session, role_id: int, menu_ids: list[int], operator: SysUser) -> None:
    role = get_role(db, role_id)
    valid_ids = set(db.scalars(select(SysMenu.id).where(SysMenu.id.in_(menu_ids), SysMenu.status != 2)).all())
    invalid = set(menu_ids) - valid_ids
    if invalid:
        raise HTTPException(status_code=422, detail="存在无效的菜单ID")
    db.execute(SysRoleMenuRelation.__table__.delete().where(SysRoleMenuRelation.role_id == role_id))
    for mid in valid_ids:
        db.add(SysRoleMenuRelation(role_id=role_id, menu_id=mid))
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="角色管理",
              action="菜单授权", params={"role_id": role_id, "menu_count": len(valid_ids)}, result=1)


def get_role_menu_ids(db: Session, role_id: int) -> list[int]:
    """角色已授权菜单 ID（过滤软删菜单，供前端回显）。"""
    get_role(db, role_id)
    return list(
        db.scalars(
            select(SysRoleMenuRelation.menu_id)
            .join(SysMenu, SysMenu.id == SysRoleMenuRelation.menu_id)
            .where(SysRoleMenuRelation.role_id == role_id, SysMenu.status != 2)
        ).all()
    )
