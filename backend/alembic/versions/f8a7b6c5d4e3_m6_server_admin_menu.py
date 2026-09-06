"""M6-T6 AI助手服务器管理：ai:server_admin 权限码 + AI助手下按钮型子菜单，授予管理员角色。

Revision ID: f8a7b6c5d4e3
Revises: e7f6a5b4c3d2
Create Date: 2026-09-06

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "f8a7b6c5d4e3"
down_revision: Union[str, Sequence[str], None] = "e7f6a5b4c3d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION = ("服务器管理", "ai:server_admin", "AI助手")
GRANT_ROLE_CODES = ["admin"]  # super_admin 经 is_super_admin 自动持有全部权限码


def _id(bind, table: str, field: str, value) -> int:
    return bind.execute(
        sa.text(f"SELECT id FROM {table} WHERE {field} = :v"), {"v": value}
    ).scalar_one()


def _role_id(bind, code: str) -> int:
    return bind.execute(sa.text("SELECT id FROM sys_role WHERE code = :c"), {"c": code}).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    now = datetime.now()
    bind = op.get_bind()

    # 1) 权限码
    op.bulk_insert(
        sa.table(
            "sys_permission",
            sa.column("name", sa.String), sa.column("code", sa.String),
            sa.column("module", sa.String), sa.column("description", sa.String),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [{"name": PERMISSION[0], "code": PERMISSION[1], "module": PERMISSION[2],
          "description": PERMISSION[0], "status": 1, "created_at": now, "updated_at": now}],
    )

    # 2) AI助手 页面下的按钮型子菜单（不显示在侧边栏，仅承载权限）
    ai_chat_menu_id = _id(bind, "sys_menu", "name", "AI助手")
    op.bulk_insert(
        sa.table(
            "sys_menu",
            sa.column("parent_id", sa.BigInteger), sa.column("name", sa.String),
            sa.column("type", mysql.TINYINT), sa.column("path", sa.String),
            sa.column("component", sa.String), sa.column("icon", sa.String),
            sa.column("permission_code", sa.String), sa.column("visible", mysql.TINYINT),
            sa.column("is_external", mysql.TINYINT), sa.column("sort_order", sa.Integer),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [{"parent_id": ai_chat_menu_id, "name": "服务器管理", "type": 3, "path": None,
          "component": None, "icon": None, "permission_code": PERMISSION[1],
          "visible": 1, "is_external": 0, "sort_order": 1, "status": 1,
          "created_at": now, "updated_at": now}],
    )
    menu_id = bind.execute(
        sa.text("SELECT id FROM sys_menu WHERE name = :n AND type = 3"),
        {"n": "服务器管理"},
    ).scalar_one()
    permission_id = _id(bind, "sys_permission", "code", PERMISSION[1])

    # 3) 菜单-权限关联
    op.bulk_insert(
        sa.table(
            "sys_menu_permission_relation",
            sa.column("menu_id", sa.BigInteger), sa.column("permission_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [{"menu_id": menu_id, "permission_id": permission_id, "created_at": now}],
    )

    # 4) 授权管理员角色（普通员工不带该子菜单，AI助手会话中不注入服务器管理工具）
    op.bulk_insert(
        sa.table(
            "sys_role_menu_relation",
            sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [{"role_id": _role_id(bind, code), "menu_id": menu_id, "created_at": now}
         for code in GRANT_ROLE_CODES],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    permission_id = _id(bind, "sys_permission", "code", PERMISSION[1])
    menu_id = bind.execute(
        sa.text("SELECT id FROM sys_menu WHERE name = :n AND type = 3"),
        {"n": "服务器管理"},
    ).scalar_one()
    role_ids = [_role_id(bind, c) for c in GRANT_ROLE_CODES]
    bind.execute(
        sa.text("DELETE FROM sys_role_menu_relation WHERE menu_id = :m AND role_id IN :rids")
        .bindparams(sa.bindparam("rids", expanding=True)),
        {"m": menu_id, "rids": role_ids},
    )
    bind.execute(
        sa.text("DELETE FROM sys_menu_permission_relation WHERE menu_id = :m AND permission_id = :p"),
        {"m": menu_id, "p": permission_id},
    )
    bind.execute(sa.text("DELETE FROM sys_menu WHERE id = :m"), {"m": menu_id})
    bind.execute(sa.text("DELETE FROM sys_permission WHERE id = :p"), {"p": permission_id})
