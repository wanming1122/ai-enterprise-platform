"""M4-T1 模型配置：ai_model 表、AI智能中心"模型配置"菜单与权限码。

Revision ID: a8b7c6d5e4f3
Revises: f7a6b8c9d0e1
Create Date: 2026-09-05

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a8b7c6d5e4f3"
down_revision: Union[str, Sequence[str], None] = "f7a6b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (parent_name, name, type, path, component, icon, permission_code, sort_order)
MODEL_MENUS = [
    ("AI智能中心", "模型配置", 2, "/ai/model", "views/ai/model/index", None, "model:list", 3),
    ("模型配置", "新增模型", 3, None, None, None, "model:create", 1),
    ("模型配置", "编辑模型", 3, None, None, None, "model:update", 2),
    ("模型配置", "删除模型", 3, None, None, None, "model:delete", 3),
    ("模型配置", "连通性测试", 3, None, None, None, "model:test", 4),
]

GRANT_ROLE_CODES = ["super_admin", "admin"]

# (code, name, module)
MODEL_PERMISSIONS = [
    ("model:list", "模型查询", "模型配置"),
    ("model:create", "新增模型", "模型配置"),
    ("model:update", "编辑模型", "模型配置"),
    ("model:delete", "删除模型", "模型配置"),
    ("model:test", "连通性测试", "模型配置"),
]

MENU_PERM_MAP = {
    "模型配置": "model:list",
    "新增模型": "model:create",
    "编辑模型": "model:update",
    "删除模型": "model:delete",
    "连通性测试": "model:test",
}


def _id(bind, table: str, field: str, value) -> int:
    return bind.execute(
        sa.text(f"SELECT id FROM {table} WHERE {field} = :v"), {"v": value}
    ).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    now = datetime.now()
    bind = op.get_bind()

    # ---------- 1. 建表 ----------
    op.create_table(
        "ai_model",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("model_type", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("api_key", sa.String(length=255), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("is_default", mysql.TINYINT(), nullable=True, server_default="0"),
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_aimodel_type_status", "model_type", "status"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )

    # ---------- 2. 菜单：AI智能中心 → 模型配置 ----------
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
            for _, name, mtype, path, component, icon, pcode, sort in MODEL_MENUS
        ],
    )
    for parent_name, name, *_ in MODEL_MENUS:
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
            for code, pname, module in MODEL_PERMISSIONS
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
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in MODEL_MENUS]
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
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in MODEL_MENUS]
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
    perm_codes = [code for code, _, _ in MODEL_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM sys_permission WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": perm_codes},
    )
    op.drop_table("ai_model")
