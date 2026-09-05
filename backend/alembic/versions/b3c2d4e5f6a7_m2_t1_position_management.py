"""M2-T1 职位管理：sys_position 表、sys_user.position_id、职位菜单/权限码/角色授权与预置职位。

Revision ID: b3c2d4e5f6a7
Revises: a1f2e3d4c5b6
Create Date: 2026-09-05

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "b3c2d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1f2e3d4c5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name, code, level, base_salary, role_code, description)
POSITIONS = [
    ("技术经理", "tech_manager", 5, "25000.00", "admin", "负责技术部团队管理与技术方案评审"),
    ("软件工程师", "software_engineer", 3, "15000.00", "employee", "负责系统开发与日常迭代"),
    ("销售专员", "sales_specialist", 2, "8000.00", "employee", "负责客户开拓与订单跟进"),
    ("人事专员", "hr_specialist", 2, "9000.00", "employee", "负责招聘、考勤与员工关系"),
    ("财务专员", "finance_specialist", 2, "9000.00", "employee", "负责报销审核与账务处理"),
    ("行政前台", "receptionist", 1, "6000.00", None, "负责前台接待与行政事务"),
]

# (parent_name, name, type, path, component, permission_code, sort_order)
POSITION_MENUS = [
    ("组织管理", "职位管理", 2, "/org/positions", "views/org/position/index", "position:list", 4),
    ("职位管理", "新增职位", 3, None, None, "position:create", 1),
    ("职位管理", "编辑职位", 3, None, None, "position:update", 2),
    ("职位管理", "删除职位", 3, None, None, "position:delete", 3),
]

# 授予职位管理菜单的角色
GRANT_ROLE_CODES = ["super_admin", "admin"]

# (code, name, module)
POSITION_PERMISSIONS = [
    ("position:list", "职位列表查询", "职位"),
    ("position:create", "新增职位", "职位"),
    ("position:update", "编辑职位", "职位"),
    ("position:delete", "删除职位", "职位"),
]


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
        "sys_position",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("level", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("base_salary", sa.Numeric(10, 2), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uk_position_name"),
        sa.UniqueConstraint("code", name="uk_position_code"),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"], name="fk_position_role"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )

    # ---------- 2. sys_user 增加 position_id ----------
    op.add_column("sys_user", sa.Column("position_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_user_position", "sys_user", "sys_position", ["position_id"], ["id"])
    op.create_index("ix_user_position", "sys_user", ["position_id"])

    # ---------- 3. 预置职位（绑定角色即权限模板） ----------
    op.bulk_insert(
        sa.table(
            "sys_position",
            sa.column("name", sa.String), sa.column("code", sa.String),
            sa.column("level", mysql.TINYINT), sa.column("base_salary", sa.Numeric),
            sa.column("role_id", sa.BigInteger), sa.column("description", sa.String),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "name": name, "code": code, "level": level, "base_salary": salary,
                "role_id": _id(bind, "sys_role", "code", role_code) if role_code else None,
                "description": desc, "status": 1, "created_at": now, "updated_at": now,
            }
            for name, code, level, salary, role_code, desc in POSITIONS
        ],
    )

    # ---------- 4. 菜单：职位管理页面 + 按钮（插入组织管理下，部门管理之后） ----------
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
            for parent_name, name, mtype, path, component, pcode, sort in POSITION_MENUS
        ],
    )
    # 按钮节点回填父级为职位管理页面；页面节点排序顺延后续菜单
    position_menu_id = _id(bind, "sys_menu", "name", "职位管理")
    for parent_name, name, *_ in POSITION_MENUS:
        if parent_name == "职位管理":
            bind.execute(
                sa.text("UPDATE sys_menu SET parent_id = :p WHERE id = :i"),
                {"p": position_menu_id, "i": _id(bind, "sys_menu", "name", name)},
            )
    for name, sort in [("角色管理", 5), ("菜单管理", 6), ("入职邀请管理", 7)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
        )

    # ---------- 5. 权限码字典 + 菜单-权限关联 ----------
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
            for code, pname, module in POSITION_PERMISSIONS
        ],
    )
    menu_perm_map = {
        "职位管理": "position:list",
        "新增职位": "position:create",
        "编辑职位": "position:update",
        "删除职位": "position:delete",
    }
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
            for menu_name, code in menu_perm_map.items()
        ],
    )

    # ---------- 6. 角色授权（超级管理员/普通管理员） ----------
    op.bulk_insert(
        sa.table(
            "sys_role_menu_relation",
            sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"role_id": _id(bind, "sys_role", "code", role_code), "menu_id": menu_id, "created_at": now}
            for role_code in GRANT_ROLE_CODES
            for menu_id in [position_menu_id]
            + [_id(bind, "sys_menu", "name", n) for _, n, *_ in POSITION_MENUS[1:]]
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in POSITION_MENUS]
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
    perm_codes = [code for code, _, _ in POSITION_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM sys_permission WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": perm_codes},
    )
    bind.execute(sa.text("DELETE FROM sys_position"))
    for name, sort in [("角色管理", 4), ("菜单管理", 5), ("入职邀请管理", 6)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
        )
    op.drop_index("ix_user_position", table_name="sys_user")
    op.drop_constraint("fk_user_position", "sys_user", type_="foreignkey")
    op.drop_column("sys_user", "position_id")
    op.drop_table("sys_position")
