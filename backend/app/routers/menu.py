"""菜单路由：菜单树 CRUD、启停、排序。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.menu import MenuCreate, MenuSortItem, MenuUpdate
from app.services import menu_service
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/menus", tags=["菜单管理"])


@router.get("/tree")
def menu_tree(
    _: SysUser = Depends(require_permissions("menu:list")),
    db: Session = Depends(get_db),
):
    """完整菜单树（目录/页面/按钮，排除软删）。"""
    return ok(menu_service.get_menu_tree(db))


@router.post("")
def create_menu(
    data: MenuCreate,
    operator: SysUser = Depends(require_permissions("menu:create")),
    db: Session = Depends(get_db),
):
    """新增菜单节点。"""
    return ok(menu_service.create_menu(db, data, operator), message="新增成功")


@router.post("/sort")
def sort_menus(
    items: list[MenuSortItem],
    operator: SysUser = Depends(require_permissions("menu:sort")),
    db: Session = Depends(get_db),
):
    """批量调整菜单排序。"""
    menu_service.update_menu_sort(db, [(i.id, i.sort_order) for i in items], operator)
    return ok(message="排序已保存")


@router.put("/{menu_id}")
def update_menu(
    menu_id: int,
    data: MenuUpdate,
    operator: SysUser = Depends(require_permissions("menu:update")),
    db: Session = Depends(get_db),
):
    """编辑菜单（含上级调整，禁止循环父子）。"""
    return ok(menu_service.update_menu(db, menu_id, data, operator), message="编辑成功")


@router.delete("/{menu_id}")
def delete_menu(
    menu_id: int,
    operator: SysUser = Depends(require_permissions("menu:delete")),
    db: Session = Depends(get_db),
):
    """软删菜单（有下级节点禁止）。"""
    menu_service.delete_menu(db, menu_id, operator)
    return ok(message="删除成功")


@router.put("/{menu_id}/status")
def toggle_status(
    menu_id: int,
    operator: SysUser = Depends(require_permissions("menu:toggle")),
    db: Session = Depends(get_db),
):
    """启停菜单。"""
    return ok(menu_service.toggle_menu_status(db, menu_id, operator), message="操作成功")
