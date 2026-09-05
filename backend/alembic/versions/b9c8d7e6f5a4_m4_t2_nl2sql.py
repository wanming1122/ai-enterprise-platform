"""M4-T2 NL2SQL：product 与 nl2sql_record 表、AI智能中心"NL2SQL"菜单与权限码。

Revision ID: b9c8d7e6f5a4
Revises: a8b7c6d5e4f3
Create Date: 2026-09-05

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "b9c8d7e6f5a4"
down_revision: Union[str, Sequence[str], None] = "a8b7c6d5e4f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 既有父菜单（M3-T1 建立的 AI智能中心目录）
P_AI = ("AI智能中心", 1)
P_NL2SQL_DIR = ("NL2SQL", 1)
P_NL2SQL_PAGE = ("NL2SQL", 2)

# (parent_key=(name,type), name, type, path, component, icon, permission_code, sort_order)
# 目录"path 留空"：避免与子页面 /ai/nl2sql 在前端侧边栏撞 antd key（前端按 path ?? id 回退）。
# 目录与页面同名"NL2SQL"，故菜单查找一律按 (name, type) 双键。
NL2SQL_MENUS = [
    (P_AI, "NL2SQL", 1, None, None, "DatabaseOutlined", None, 4),
    (P_NL2SQL_DIR, "产品数据", 2, "/ai/nl2sql/product", "views/ai/nl2sql/product/index", None, "product:list", 1),
    (P_NL2SQL_DIR, "NL2SQL", 2, "/ai/nl2sql", "views/ai/nl2sql/index", None, "nl2sql:generate", 2),
    (P_NL2SQL_DIR, "查询历史", 2, "/ai/nl2sql/history", "views/ai/nl2sql/history/index", None, "nl2sql:history", 3),
    (("产品数据", 2), "新增产品", 3, None, None, None, "product:create", 1),
    (("产品数据", 2), "编辑产品", 3, None, None, None, "product:update", 2),
    (("产品数据", 2), "删除产品", 3, None, None, None, "product:delete", 3),
    (P_NL2SQL_PAGE, "审核SQL", 3, None, None, None, "nl2sql:review", 1),
    (P_NL2SQL_PAGE, "执行SQL", 3, None, None, None, "nl2sql:execute", 2),
]

GRANT_ROLE_CODES = ["super_admin", "admin"]

# (code, name, module)
NL2SQL_PERMISSIONS = [
    ("product:list", "产品查询", "NL2SQL"),
    ("product:create", "新增产品", "NL2SQL"),
    ("product:update", "编辑产品", "NL2SQL"),
    ("product:delete", "删除产品", "NL2SQL"),
    ("nl2sql:generate", "NL2SQL生成", "NL2SQL"),
    ("nl2sql:review", "SQL审核", "NL2SQL"),
    ("nl2sql:execute", "SQL执行", "NL2SQL"),
    ("nl2sql:history", "查询历史", "NL2SQL"),
]


def _menu_id(bind, name: str, mtype: int) -> int:
    return bind.execute(
        sa.text("SELECT id FROM sys_menu WHERE name = :n AND type = :t"),
        {"n": name, "t": mtype},
    ).scalar_one()


def _perm_id(bind, code: str) -> int:
    return bind.execute(
        sa.text("SELECT id FROM sys_permission WHERE code = :c"), {"c": code}
    ).scalar_one()


def _role_id(bind, code: str) -> int:
    return bind.execute(
        sa.text("SELECT id FROM sys_role WHERE code = :c"), {"c": code}
    ).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    now = datetime.now()
    bind = op.get_bind()

    # ---------- 1. 建表 ----------
    op.create_table(
        "product",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_product_status", "status"),
        sa.Index("ix_product_category", "category"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "nl2sql_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=False),
        sa.Column("review_status", mysql.TINYINT(), nullable=True, server_default="0"),
        sa.Column("review_comment", sa.String(length=255), nullable=True),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("execution_ms", sa.Integer(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_nl2sql_user"),
        sa.Index("ix_nl2sql_status", "review_status"),
        sa.Index("ix_nl2sql_created", "created_at"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )

    # ---------- 2. 菜单：AI智能中心 → NL2SQL目录 → 页面/按钮 ----------
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
            for _, name, mtype, path, component, icon, pcode, sort in NL2SQL_MENUS
        ],
    )
    for parent_key, name, mtype, *_ in NL2SQL_MENUS:
        parent_name, parent_type = parent_key
        bind.execute(
            sa.text("UPDATE sys_menu SET parent_id = :p WHERE id = :i"),
            {"p": _menu_id(bind, parent_name, parent_type), "i": _menu_id(bind, name, mtype)},
        )

    # ---------- 3. 权限码字典 + 菜单-权限关联（按菜单定义内联取 code） ----------
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
            for code, pname, module in NL2SQL_PERMISSIONS
        ],
    )
    op.bulk_insert(
        sa.table(
            "sys_menu_permission_relation",
            sa.column("menu_id", sa.BigInteger), sa.column("permission_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"menu_id": _menu_id(bind, name, mtype), "permission_id": _perm_id(bind, pcode),
             "created_at": now}
            for _, name, mtype, _, _, _, pcode, _ in NL2SQL_MENUS if pcode
        ],
    )

    # ---------- 4. 角色授权（超级管理员/普通管理员） ----------
    menu_ids = [_menu_id(bind, name, mtype) for _, name, mtype, *_ in NL2SQL_MENUS]
    op.bulk_insert(
        sa.table(
            "sys_role_menu_relation",
            sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"role_id": _role_id(bind, role_code), "menu_id": menu_id, "created_at": now}
            for role_code in GRANT_ROLE_CODES
            for menu_id in menu_ids
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    menu_ids = [_menu_id(bind, name, mtype) for _, name, mtype, *_ in NL2SQL_MENUS]
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
    perm_codes = [code for code, _, _ in NL2SQL_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM sys_permission WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": perm_codes},
    )
    op.drop_table("nl2sql_record")
    op.drop_table("product")
