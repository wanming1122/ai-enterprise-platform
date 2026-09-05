"""M4-T3 AI助手：ai_message 补 reasoning_content、ai_conversation 补 status、AI助手菜单与权限。

Revision ID: c0d9e8f7a6b5
Revises: b9c8d7e6f5a4
Create Date: 2026-09-06

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "c0d9e8f7a6b5"
down_revision: Union[str, Sequence[str], None] = "b9c8d7e6f5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (parent_name, name, type, path, component, icon, permission_code, sort_order)
AI_MENUS = [
    ("AI智能中心", "AI助手", 2, "/ai/chat", "views/ai/chat/index", None, "ai:chat", 5),
]

GRANT_ROLE_CODES = ["super_admin", "admin"]

# (code, name, module)
AI_PERMISSIONS = [
    ("ai:chat", "AI助手对话", "AI助手"),
]

MENU_PERM_MAP = {
    "AI助手": "ai:chat",
}


def _id(bind, table: str, field: str, value) -> int:
    return bind.execute(
        sa.text(f"SELECT id FROM {table} WHERE {field} = :v"), {"v": value}
    ).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    now = datetime.now()
    bind = op.get_bind()

    # ---------- 1. 表结构补充 ----------
    op.add_column(
        "ai_message",
        sa.Column("reasoning_content", sa.Text(), nullable=True, comment="深度思考过程（推理模型）"),
    )
    op.add_column(
        "ai_conversation",
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="1", comment="1正常 2软删除"),
    )
    op.add_column(
        "ai_conversation",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="kb",
                  comment="会话来源：kb问答调试 / ai AI助手"),
    )

    # ---------- 2. 菜单：AI智能中心 → AI助手 ----------
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
        [
            {
                "parent_id": None, "name": name, "type": mtype, "path": path,
                "component": component, "icon": icon, "permission_code": pcode,
                "visible": 1, "is_external": 0, "sort_order": sort, "status": 1,
                "created_at": now, "updated_at": now,
            }
            for _, name, mtype, path, component, icon, pcode, sort in AI_MENUS
        ],
    )
    for parent_name, name, *_ in AI_MENUS:
        bind.execute(
            sa.text("UPDATE sys_menu SET parent_id = :p WHERE id = :i"),
            {"p": _id(bind, "sys_menu", "name", parent_name), "i": _id(bind, "sys_menu", "name", name)},
        )

    # ---------- 3. 权限码字典 + 菜单-权限关联 ----------
    op.bulk_insert(
        sa.table(
            "sys_permission",
            sa.column("name", sa.String), sa.column("code", sa.String),
            sa.column("module", sa.String), sa.column("description", sa.String),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {"name": pname, "code": code, "module": module, "description": pname,
             "status": 1, "created_at": now, "updated_at": now}
            for code, pname, module in AI_PERMISSIONS
        ],
    )
    op.bulk_insert(
        sa.table(
            "sys_menu_permission_relation",
            sa.column("menu_id", sa.BigInteger), sa.column("permission_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"menu_id": _id(bind, "sys_menu", "name", menu_name),
             "permission_id": _id(bind, "sys_permission", "code", code),
             "created_at": now}
            for menu_name, code in MENU_PERM_MAP.items() if code
        ],
    )

    # ---------- 4. 角色授权（超级管理员/普通管理员） ----------
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in AI_MENUS]
    op.bulk_insert(
        sa.table(
            "sys_role_menu_relation",
            sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"role_id": _id(bind, "sys_role", "code", role_code), "menu_id": menu_id, "created_at": now}
            for role_code in GRANT_ROLE_CODES
            for menu_id in menu_ids
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in AI_MENUS]
    bind.execute(
        sa.text("DELETE FROM sys_role_menu_relation WHERE menu_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": menu_ids},
    )
    bind.execute(
        sa.text("DELETE FROM sys_menu_permission_relation WHERE menu_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": menu_ids},
    )
    bind.execute(sa.text("DELETE FROM sys_menu WHERE id IN :ids").bindparams(
        sa.bindparam("ids", expanding=True)
    ), {"ids": menu_ids})
    perm_codes = [code for code, _, _ in AI_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM sys_permission WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": perm_codes},
    )
    op.drop_column("ai_conversation", "source")
    op.drop_column("ai_conversation", "status")
    op.drop_column("ai_message", "reasoning_content")
