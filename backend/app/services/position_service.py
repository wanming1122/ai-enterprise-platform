"""职位服务：CRUD、启停、下拉选项，以及职位绑定角色的权限模板联动。"""
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.position import SysPosition
from app.models.role import SysRole
from app.models.user import SysUser
from app.schemas.position import PositionCreate, PositionUpdate
from app.services.operation_log_service import write_log

CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _check_unique(db: Session, field: str, value: str, exclude_id: int | None = None) -> None:
    q = select(SysPosition.id).where(getattr(SysPosition, field) == value, SysPosition.status != 2)
    if exclude_id is not None:
        q = q.where(SysPosition.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(status_code=422, detail="职位名称或编码已存在")


def _validate_role(db: Session, role_id: int | None) -> None:
    if role_id is not None:
        role = db.get(SysRole, role_id)
        if role is None or role.status == 2:
            raise HTTPException(status_code=422, detail="绑定的角色不存在")


def serialize_position(db: Session, p: SysPosition) -> dict:
    role_name = None
    if p.role_id:
        role = db.get(SysRole, p.role_id)
        role_name = role.name if role and role.status != 2 else None
    user_count = db.scalar(
        select(func.count()).select_from(SysUser).where(
            SysUser.position_id == p.id, SysUser.status != 2
        )
    ) or 0
    return {
        "id": p.id,
        "name": p.name,
        "code": p.code,
        "level": p.level,
        "base_salary": str(p.base_salary),
        "role_id": p.role_id,
        "role_name": role_name,
        "description": p.description,
        "status": p.status,
        "user_count": user_count,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def list_positions(
    db: Session,
    *,
    keyword: str | None = None,
    role_id: int | None = None,
    status: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    q = select(SysPosition).where(SysPosition.status != 2)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(SysPosition.name.like(like), SysPosition.code.like(like)))
    if role_id:
        q = q.where(SysPosition.role_id == role_id)
    if status is not None:
        q = q.where(SysPosition.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    positions = db.scalars(
        q.order_by(SysPosition.level.desc(), SysPosition.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_position(db, p) for p in positions], total


def get_position(db: Session, position_id: int) -> SysPosition:
    position = db.get(SysPosition, position_id)
    if position is None or position.status == 2:
        raise HTTPException(status_code=404, detail="职位不存在")
    return position


def create_position(db: Session, data: PositionCreate, operator: SysUser) -> dict:
    if not CODE_PATTERN.match(data.code):
        raise HTTPException(status_code=422, detail="职位编码需以字母开头，仅含字母数字下划线")
    _check_unique(db, "name", data.name)
    _check_unique(db, "code", data.code)
    _validate_role(db, data.role_id)
    if data.base_salary < Decimal("0"):
        raise HTTPException(status_code=422, detail="基本工资不能为负数")
    position = SysPosition(
        name=data.name, code=data.code, level=data.level,
        base_salary=data.base_salary, role_id=data.role_id,
        description=data.description, status=data.status,
    )
    db.add(position)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="职位管理",
              action="新增职位", params=data.model_dump(mode="json"), result=1)
    return serialize_position(db, position)


def update_position(db: Session, position_id: int, data: PositionUpdate, operator: SysUser) -> dict:
    position = get_position(db, position_id)
    updates = data.model_dump(exclude_unset=True)
    if "code" in updates and updates["code"]:
        if not CODE_PATTERN.match(updates["code"]):
            raise HTTPException(status_code=422, detail="职位编码需以字母开头，仅含字母数字下划线")
        _check_unique(db, "code", updates["code"], exclude_id=position_id)
    if "name" in updates and updates["name"]:
        _check_unique(db, "name", updates["name"], exclude_id=position_id)
    if "role_id" in updates:
        _validate_role(db, updates["role_id"])
    if "base_salary" in updates and updates["base_salary"] is not None:
        if updates["base_salary"] < Decimal("0"):
            raise HTTPException(status_code=422, detail="基本工资不能为负数")
    for field, value in updates.items():
        setattr(position, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="职位管理",
              action="编辑职位", params={"id": position_id, **data.model_dump(mode="json", exclude_unset=True)}, result=1)
    return serialize_position(db, position)


def delete_position(db: Session, position_id: int, operator: SysUser) -> None:
    position = get_position(db, position_id)
    bound = db.scalar(
        select(func.count()).select_from(SysUser).where(
            SysUser.position_id == position_id, SysUser.status != 2
        )
    ) or 0
    if bound:
        raise HTTPException(status_code=422, detail=f"仍有 {bound} 名员工绑定该职位，请先调整后再删除")
    position.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="职位管理",
              action="删除职位", params={"id": position_id}, result=1)


def toggle_status(db: Session, position_id: int, operator: SysUser) -> dict:
    position = get_position(db, position_id)
    position.status = 0 if position.status == 1 else 1
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="职位管理",
              action="启停职位", params={"id": position_id, "status": position.status}, result=1)
    return serialize_position(db, position)


def list_options(db: Session) -> list[dict]:
    """启用职位下拉（供用户管理等选择，含薪资与绑定角色便于前端提示）。"""
    positions = db.scalars(
        select(SysPosition).where(SysPosition.status == 1).order_by(SysPosition.level.desc(), SysPosition.id)
    ).all()
    role_ids = {p.role_id for p in positions if p.role_id}
    role_names = {}
    if role_ids:
        role_names = dict(
            db.execute(select(SysRole.id, SysRole.name).where(SysRole.id.in_(role_ids))).all()
        )
    return [
        {
            "id": p.id,
            "name": p.name,
            "level": p.level,
            "base_salary": str(p.base_salary),
            "role_id": p.role_id,
            "role_name": role_names.get(p.role_id) if p.role_id else None,
        }
        for p in positions
    ]


def sync_position_role(db: Session, user_id: int, old_position_id: int | None,
                       new_position_id: int | None) -> None:
    """职位角色联动：换职位时移除旧职位角色、并入新职位绑定的角色，手动分配的其他角色保留。

    依赖调用方在提交前传入变更前后的 position_id；仅提交事务、不写审计（由用户服务统一记录）。
    """
    from app.models.user_role_relation import SysUserRoleRelation

    if old_position_id == new_position_id:
        return
    current = set(
        db.scalars(select(SysUserRoleRelation.role_id).where(SysUserRoleRelation.user_id == user_id)).all()
    )

    def position_role(position_id: int | None) -> int | None:
        if position_id is None:
            return None
        position = db.get(SysPosition, position_id)
        return position.role_id if position and position.status != 2 else None

    old_role = position_role(old_position_id)
    new_role = position_role(new_position_id)
    if old_role and old_role != new_role:
        current.discard(old_role)
    if new_role:
        current.add(new_role)

    db.execute(
        SysUserRoleRelation.__table__.delete().where(SysUserRoleRelation.user_id == user_id)
    )
    for rid in current:
        db.add(SysUserRoleRelation(user_id=user_id, role_id=rid))
    db.flush()
