"""M2-T3 薪资管理：sal_payroll/sal_adjustment 表、薪资菜单与权限码。

Revision ID: d5e4f6a7b8c9
Revises: c4d3e5f6a7b8
Create Date: 2026-09-05

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "d5e4f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c4d3e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (parent_name, name, type, path, component, permission_code, sort_order)
SAL_MENUS = [
    ("组织管理", "薪资管理", 2, "/org/salaries", "views/salary/index", "salary:list", 7),
    ("薪资管理", "奖惩录入", 3, None, None, "salary:adjust", 1),
    ("薪资管理", "生成工资单", 3, None, None, "salary:generate", 2),
    ("薪资管理", "确认工资单", 3, None, None, "salary:confirm", 3),
    ("薪资管理", "发放工资单", 3, None, None, "salary:pay", 4),
]

GRANT_ROLE_CODES = ["super_admin", "admin"]

# (code, name, module)
SAL_PERMISSIONS = [
    ("salary:list", "工资单查询", "薪资"),
    ("salary:adjust", "奖惩录入", "薪资"),
    ("salary:generate", "生成工资单", "薪资"),
    ("salary:confirm", "确认工资单", "薪资"),
    ("salary:pay", "发放工资单", "薪资"),
]

MENU_PERM_MAP = {
    "薪资管理": "salary:list",
    "奖惩录入": "salary:adjust",
    "生成工资单": "salary:generate",
    "确认工资单": "salary:confirm",
    "发放工资单": "salary:pay",
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
        "sal_payroll",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column("position_name", sa.String(length=64), nullable=False),
        sa.Column("base_salary", sa.Numeric(10, 2), nullable=False),
        sa.Column("attendance_adjust", sa.Numeric(10, 2), nullable=True, server_default="0"),
        sa.Column("manual_adjust", sa.Numeric(10, 2), nullable=True, server_default="0"),
        sa.Column("total_salary", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="0"),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year_month", name="uk_sal_user_month"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_sal_user"),
        sa.Index("ix_sal_payroll_month", "year_month"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sal_adjustment",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("adjust_type", mysql.TINYINT(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_sal_adj_user"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )

    # ---------- 2. 菜单：薪资管理页面 + 按钮（组织管理下，考勤规则之后） ----------
    org_menu_id = _id(bind, "sys_menu", "name", "组织管理")
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
                "parent_id": org_menu_id if parent_name == "组织管理" else None,
                "name": name, "type": mtype, "path": path, "component": component,
                "icon": None, "permission_code": pcode, "visible": 1, "is_external": 0,
                "sort_order": sort, "status": 1, "created_at": now, "updated_at": now,
            }
            for parent_name, name, mtype, path, component, pcode, sort in SAL_MENUS
        ],
    )
    for parent_name, name, *_ in SAL_MENUS:
        if parent_name not in ("组织管理",):
            bind.execute(
                sa.text("UPDATE sys_menu SET parent_id = :p WHERE id = :i"),
                {"p": _id(bind, "sys_menu", "name", parent_name), "i": _id(bind, "sys_menu", "name", name)},
            )
    for name, sort in [("角色管理", 8), ("菜单管理", 9), ("入职邀请管理", 10)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
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
            for code, pname, module in SAL_PERMISSIONS
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
            for menu_name, code in MENU_PERM_MAP.items()
        ],
    )

    # ---------- 4. 角色授权（超级管理员/普通管理员） ----------
    sal_menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in SAL_MENUS]
    op.bulk_insert(
        sa.table(
            "sys_role_menu_relation",
            sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"role_id": _id(bind, "sys_role", "code", role_code), "menu_id": menu_id, "created_at": now}
            for role_code in GRANT_ROLE_CODES
            for menu_id in sal_menu_ids
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in SAL_MENUS]
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
    perm_codes = [code for code, _, _ in SAL_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM sys_permission WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": perm_codes},
    )
    for name, sort in [("角色管理", 7), ("菜单管理", 8), ("入职邀请管理", 9)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
        )
    op.drop_table("sal_adjustment")
    op.drop_table("sal_payroll")
