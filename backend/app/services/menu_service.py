"""菜单服务：构建用户授权菜单树、汇总权限标识，供登录与动态路由复用。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.menu import SysMenu
from app.models.menu_permission_relation import SysMenuPermissionRelation
from app.models.role import SysRole
from app.models.role_menu_relation import SysRoleMenuRelation
from app.models.user_role_relation import SysUserRoleRelation
from app.models.permission import SysPermission

_TYPE_TEXT = {1: "dir", 2: "page", 3: "button"}


def is_super_admin(db: Session, user_id: int) -> bool:
    """用户是否绑定超级管理员角色（role_type=1）。"""
    return (
        db.scalar(
            select(SysRole.id)
            .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
            .where(SysUserRoleRelation.user_id == user_id, SysRole.role_type == 1)
        )
        is not None
    )


def _authorized_menu_ids(db: Session, user_id: int) -> list[int]:
    """返回用户绑定角色授权范围内的菜单 ID。"""
    return list(
        db.scalars(
            select(SysRoleMenuRelation.menu_id)
            .join(SysRole, SysRole.id == SysRoleMenuRelation.role_id)
            .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
            .where(SysUserRoleRelation.user_id == user_id)
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
            .where(SysMenuPermissionRelation.menu_id.in_(authorized), SysPermission.status == 1)
        ).all()
    )
    return sorted(menu_codes | rel_codes)
