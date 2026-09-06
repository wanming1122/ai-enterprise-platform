"""字典管理路由（M5 补齐）：字典类型与字典项两级维护。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.dict import DictItemCreate, DictItemUpdate, DictTypeCreate, DictTypeUpdate
from app.services import dict_service
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/dict-types", tags=["字典管理"])


@router.get("")
def list_types(
    _: SysUser = Depends(require_permissions("dict:list")),
    db: Session = Depends(get_db),
):
    """字典类型列表（含字典项数量）。"""
    return ok(dict_service.list_types(db))


@router.post("")
def create_type(
    data: DictTypeCreate,
    operator: SysUser = Depends(require_permissions("dict:create")),
    db: Session = Depends(get_db),
):
    """新增字典类型。"""
    return ok(dict_service.create_type(db, data, operator), message="新增成功")


@router.put("/{type_id}")
def update_type(
    type_id: int,
    data: DictTypeUpdate,
    operator: SysUser = Depends(require_permissions("dict:update")),
    db: Session = Depends(get_db),
):
    """编辑字典类型。"""
    return ok(dict_service.update_type(db, type_id, data, operator), message="保存成功")


@router.delete("/{type_id}")
def delete_type(
    type_id: int,
    operator: SysUser = Depends(require_permissions("dict:delete")),
    db: Session = Depends(get_db),
):
    """删除字典类型（级联软删其字典项）。"""
    dict_service.delete_type(db, type_id, operator)
    return ok(message="删除成功")


@router.get("/{type_id}/items")
def list_items(
    type_id: int,
    _: SysUser = Depends(require_permissions("dict:list")),
    db: Session = Depends(get_db),
):
    """字典项列表。"""
    return ok(dict_service.list_items(db, type_id))


@router.post("/{type_id}/items")
def create_item(
    type_id: int,
    data: DictItemCreate,
    operator: SysUser = Depends(require_permissions("dict:update")),
    db: Session = Depends(get_db),
):
    """新增字典项。"""
    return ok(dict_service.create_item(db, type_id, data, operator), message="新增成功")


@router.put("/items/{item_id}")
def update_item(
    item_id: int,
    data: DictItemUpdate,
    operator: SysUser = Depends(require_permissions("dict:update")),
    db: Session = Depends(get_db),
):
    """编辑字典项。"""
    return ok(dict_service.update_item(db, item_id, data, operator), message="保存成功")


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    operator: SysUser = Depends(require_permissions("dict:delete")),
    db: Session = Depends(get_db),
):
    """删除字典项（软删除）。"""
    dict_service.delete_item(db, item_id, operator)
    return ok(message="删除成功")
