"""字典管理服务（M5 补齐）：字典类型与字典项两级维护。"""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dict import SysDictItem, SysDictType
from app.models.user import SysUser
from app.schemas.dict import DictItemCreate, DictItemUpdate, DictTypeCreate, DictTypeUpdate
from app.services.operation_log_service import write_log


def serialize_type(db: Session, t: SysDictType) -> dict:
    item_count = db.scalar(
        select(func.count()).select_from(SysDictItem).where(
            SysDictItem.dict_code == t.dict_code, SysDictItem.status != 2
        )
    ) or 0
    return {
        "id": t.id,
        "dict_name": t.dict_name,
        "dict_code": t.dict_code,
        "description": t.description,
        "status": t.status,
        "item_count": int(item_count),
        "created_at": t.created_at.isoformat(),
    }


def serialize_item(i: SysDictItem) -> dict:
    return {
        "id": i.id,
        "dict_code": i.dict_code,
        "item_label": i.item_label,
        "item_value": i.item_value,
        "sort_order": i.sort_order,
        "status": i.status,
    }


def _get_type(db: Session, type_id: int) -> SysDictType:
    t = db.get(SysDictType, type_id)
    if t is None or t.status == 2:
        raise HTTPException(status_code=404, detail="字典类型不存在")
    return t


def list_types(db: Session) -> list[dict]:
    items = db.scalars(
        select(SysDictType).where(SysDictType.status != 2).order_by(SysDictType.id)
    ).all()
    return [serialize_type(db, t) for t in items]


def create_type(db: Session, data: DictTypeCreate, operator: SysUser) -> dict:
    exists = db.scalar(
        select(SysDictType).where(
            SysDictType.dict_code == data.dict_code, SysDictType.status != 2
        )
    )
    if exists is not None:
        raise HTTPException(status_code=422, detail="字典编码已存在")
    t = SysDictType(**data.model_dump())
    db.add(t)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="字典管理",
              action="新增字典类型", params=data.model_dump(), result=1)
    return serialize_type(db, t)


def update_type(db: Session, type_id: int, data: DictTypeUpdate, operator: SysUser) -> dict:
    t = _get_type(db, type_id)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("status") == 1 and t.status == 1:
        updates.pop("status")
    for field, value in updates.items():
        setattr(t, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="字典管理",
              action="编辑字典类型", params={"id": type_id, **updates}, result=1)
    return serialize_type(db, t)


def delete_type(db: Session, type_id: int, operator: SysUser) -> None:
    t = _get_type(db, type_id)
    # 软删类型并级联软删其字典项
    for item in db.scalars(select(SysDictItem).where(SysDictItem.dict_code == t.dict_code)).all():
        item.status = 2
    t.status = 2
    # 释放唯一键占用（uk_dict_code）：软删行仍占物理唯一索引，同编码无法重建
    suffix = f"_deleted_{t.id}"
    if not t.dict_code.endswith(suffix):
        t.dict_code = f"{t.dict_code[:64 - len(suffix)]}{suffix}"
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="字典管理",
              action="删除字典类型", params={"id": type_id, "code": t.dict_code}, result=1)


def list_items(db: Session, type_id: int) -> list[dict]:
    t = _get_type(db, type_id)
    items = db.scalars(
        select(SysDictItem)
        .where(SysDictItem.dict_code == t.dict_code, SysDictItem.status != 2)
        .order_by(SysDictItem.sort_order, SysDictItem.id)
    ).all()
    return [serialize_item(i) for i in items]


def create_item(db: Session, type_id: int, data: DictItemCreate, operator: SysUser) -> dict:
    t = _get_type(db, type_id)
    dup = db.scalar(
        select(SysDictItem).where(
            SysDictItem.dict_code == t.dict_code,
            SysDictItem.item_value == data.item_value,
            SysDictItem.status != 2,
        )
    )
    if dup is not None:
        raise HTTPException(status_code=422, detail="该字典项值已存在")
    item = SysDictItem(dict_code=t.dict_code, **data.model_dump())
    db.add(item)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="字典管理",
              action="新增字典项", params={"type_id": type_id, **data.model_dump()}, result=1)
    return serialize_item(item)


def _get_item(db: Session, item_id: int) -> SysDictItem:
    item = db.get(SysDictItem, item_id)
    if item is None or item.status == 2:
        raise HTTPException(status_code=404, detail="字典项不存在")
    return item


def update_item(db: Session, item_id: int, data: DictItemUpdate, operator: SysUser) -> dict:
    item = _get_item(db, item_id)
    updates = data.model_dump(exclude_unset=True)
    if "item_value" in updates:
        dup = db.scalar(
            select(SysDictItem).where(
                SysDictItem.dict_code == item.dict_code,
                SysDictItem.item_value == updates["item_value"],
                SysDictItem.status != 2,
                SysDictItem.id != item.id,
            )
        )
        if dup is not None:
            raise HTTPException(status_code=422, detail="该字典项值已存在")
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="字典管理",
              action="编辑字典项", params={"id": item_id, **updates}, result=1)
    return serialize_item(item)


def delete_item(db: Session, item_id: int, operator: SysUser) -> None:
    item = _get_item(db, item_id)
    item.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="字典管理",
              action="删除字典项", params={"id": item_id}, result=1)
