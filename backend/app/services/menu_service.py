"""菜单服务：构建用户授权菜单树、汇总权限标识、菜单 CRUD，供登录与动态路由复用。"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.menu import SysMenu
from app.models.menu_permission_relation import SysMenuPermissionRelation
from app.models.role import SysRole
from app.models.role_menu_relation import SysRoleMenuRelation
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
from app.models.permission import SysPermission
from app.schemas.menu import MenuCreate, MenuUpdate
from app.services.operation_log_service import write_log

_TYPE_TEXT = {1: "dir", 2: "page", 3: "button"}


def is_super_admin(db: Session, user_id: int) -> bool:
    """用户是否绑定启用中的超级管理员角色（role_type=1；停用/软删角色不生效）。"""
    return (
        db.scalar(
            select(SysRole.id)
            .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
            .where(SysUserRoleRelation.user_id == user_id, SysRole.role_type == 1, SysRole.status == 1)
        )
        is not None
    )


def is_admin_user(db: Session, user_id: int) -> bool:
    """用户是否绑定启用中的管理员角色（超级管理员 role_type=1 或普通管理员 role_type=2）。"""
    return (
        db.scalar(
            select(SysRole.id)
            .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
            .where(
                SysUserRoleRelation.user_id == user_id,
                SysRole.role_type.in_([1, 2]),
                SysRole.status == 1,
            )
        )
        is not None
    )


def _authorized_menu_ids(db: Session, user_id: int) -> list[int]:
    """返回用户绑定角色授权范围内的菜单 ID（仅统计启用中的角色，停用/软删即回收权限）。"""
    return list(
        db.scalars(
            select(SysRoleMenuRelation.menu_id)
            .join(SysRole, SysRole.id == SysRoleMenuRelation.role_id)
            .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
            .where(SysUserRoleRelation.user_id == user_id, SysRole.status == 1)
        ).all()
    )


def build_menu_tree(db: Session, user_id: int) -> list[dict]:
    """构建用户可见菜单树（目录+页面，不含按钮；按 sort_order 排序）。"""
    if is_super_admin(db, user_id):
        menu_rows = db.scalars(
            select(SysMenu).where(SysMenu.status == 1, SysMenu.visible == 1, SysMenu.type.in_([1, 2]))
        ).all()
    else:
        authorized = set(_authorized_menu_ids(db, user_id))
        menu_rows = [
            m for m in db.scalars(
                select(SysMenu).where(SysMenu.status == 1, SysMenu.visible == 1, SysMenu.type.in_([1, 2]))
            ).all()
            if m.id in authorized
        ]

    nodes: dict[int, dict] = {}
    for m in sorted(menu_rows, key=lambda x: (x.sort_order, x.id)):
        nodes[m.id] = {
            "id": m.id,
            "parent_id": m.parent_id,
            "name": m.name,
            "path": m.path,
            "component": m.component,
            "icon": m.icon,
            "type": _TYPE_TEXT.get(m.type, "page"),
            "sort_order": m.sort_order,
            "children": [],
        }

    roots: list[dict] = []
    for node in nodes.values():
        if node["parent_id"] is not None and node["parent_id"] in nodes:
            nodes[node["parent_id"]]["children"].append(node)
        else:
            roots.append(node)
    return roots


def collect_permissions(db: Session, user_id: int) -> list[str]:
    """汇总用户全部权限标识（菜单自带 permission_code + 菜单关联权限表）。"""
    if is_super_admin(db, user_id):
        codes = set(db.scalars(select(SysPermission.code).where(SysPermission.status == 1)).all())
        return sorted(codes)

    authorized = set(_authorized_menu_ids(db, user_id))
    if not authorized:
        return []

    menu_codes = set(
        db.scalars(
            select(SysMenu.permission_code).where(
                SysMenu.id.in_(authorized),
                SysMenu.permission_code.is_not(None),
                SysMenu.status == 1,
            )
        ).all()
    )
    rel_codes = set(
        db.scalars(
            select(SysPermission.code)
            .join(SysMenuPermissionRelation, SysMenuPermissionRelation.permission_id == SysPermission.id)
            .join(SysMenu, SysMenu.id == SysMenuPermissionRelation.menu_id)
            .where(
                SysMenuPermissionRelation.menu_id.in_(authorized),
                SysPermission.status == 1,
                SysMenu.status == 1,  # 停用/软删菜单的关联权限一并回收
            )
        ).all()
    )
    return sorted(menu_codes | rel_codes)


# ---------- 菜单管理（M1-T5） ----------

def serialize_menu(m: SysMenu) -> dict:
    return {
        "id": m.id,
        "parent_id": m.parent_id,
        "name": m.name,
        "type": m.type,
        "path": m.path,
        "component": m.component,
        "icon": m.icon,
        "permission_code": m.permission_code,
        "visible": m.visible,
        "is_external": m.is_external,
        "sort_order": m.sort_order,
        "status": m.status,
        "children": [],
    }


def get_menu_tree(db: Session) -> list[dict]:
    """完整菜单树（含按钮，排除软删），按 sort_order 排序。"""
    menus = db.scalars(
        select(SysMenu).where(SysMenu.status != 2).order_by(SysMenu.sort_order, SysMenu.id)
    ).all()
    nodes: dict[int, dict] = {m.id: serialize_menu(m) for m in menus}
    roots: list[dict] = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def get_menu(db: Session, menu_id: int) -> SysMenu:
    menu = db.get(SysMenu, menu_id)
    if menu is None or menu.status == 2:
        raise HTTPException(status_code=404, detail="菜单不存在")
    return menu


def _validate_menu_data(db: Session, *, name: str, mtype: int, path: str | None, permission_code: str | None, parent_id: int | None, self_id: int | None = None) -> None:
    if not name:
        raise HTTPException(status_code=422, detail="菜单名称不能为空")
    if mtype in (1, 2) and not path:
        raise HTTPException(status_code=422, detail="目录与页面菜单必须配置路由路径")
    if mtype == 3 and not permission_code:
        raise HTTPException(status_code=422, detail="功能按钮必须绑定专属权限标识")
    if parent_id is not None:
        parent = db.get(SysMenu, parent_id)
        if parent is None or parent.status == 2:
            raise HTTPException(status_code=422, detail="父菜单不存在")
        if self_id is not None:
            cur = parent
            while cur is not None:
                if cur.id == self_id:
                    raise HTTPException(status_code=422, detail="不能将菜单移动到自身或其下级")
                cur = db.get(SysMenu, cur.parent_id) if cur.parent_id else None


def create_menu(db: Session, data: MenuCreate, operator: SysUser) -> dict:
    _validate_menu_data(
        db, name=data.name, mtype=data.type, path=data.path,
        permission_code=data.permission_code, parent_id=data.parent_id,
    )
    menu = SysMenu(
        parent_id=data.parent_id, name=data.name, type=data.type, path=data.path,
        component=data.component, icon=data.icon, permission_code=data.permission_code,
        visible=data.visible, is_external=data.is_external, sort_order=data.sort_order,
        status=data.status,
    )
    db.add(menu)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="菜单管理",
              action="新增菜单", params=data.model_dump(), result=1)
    return serialize_menu(menu)


def update_menu(db: Session, menu_id: int, data: MenuUpdate, operator: SysUser) -> dict:
    menu = get_menu(db, menu_id)
    updates = data.model_dump(exclude_unset=True)
    _validate_menu_data(
        db,
        name=updates.get("name", menu.name),
        mtype=updates.get("type", menu.type),
        path=updates.get("path", menu.path),
        permission_code=updates.get("permission_code", menu.permission_code),
        parent_id=updates.get("parent_id", menu.parent_id),
        self_id=menu_id,
    )
    for field, value in updates.items():
        setattr(menu, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="菜单管理",
              action="编辑菜单", params={"id": menu_id, **updates}, result=1)
    return serialize_menu(menu)


def delete_menu(db: Session, menu_id: int, operator: SysUser) -> None:
    menu = get_menu(db, menu_id)
    child = db.scalar(select(SysMenu.id).where(SysMenu.parent_id == menu_id, SysMenu.status != 2))
    if child is not None:
        raise HTTPException(status_code=422, detail="存在下级菜单，请先处理后再删除")
    menu.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="菜单管理",
              action="删除菜单", params={"id": menu_id}, result=1)


def toggle_menu_status(db: Session, menu_id: int, operator: SysUser) -> dict:
    menu = get_menu(db, menu_id)
    menu.status = 0 if menu.status == 1 else 1
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="菜单管理",
              action="启停菜单", params={"id": menu_id, "status": menu.status}, result=1)
    return serialize_menu(menu)


def update_menu_sort(db: Session, items: list[tuple[int, int]], operator: SysUser) -> None:
    """批量更新菜单排序：items 为 [(menu_id, sort_order)]。"""
    for menu_id, sort_order in items:
        menu = db.get(SysMenu, menu_id)
        if menu is not None:
            menu.sort_order = sort_order
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="菜单管理",
              action="菜单排序", params={"count": len(items)}, result=1)
