"""M2-T2 考勤管理：att_record/att_rule 表、预置规则、考勤菜单/权限码与状态字典。

Revision ID: c4d3e5f6a7b8
Revises: b3c2d4e5f6a7
Create Date: 2026-09-05

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "c4d3e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b3c2d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (status_key, adjust_type, amount, enabled)
RULES = [
    ("normal", 1, "0.00", 0),        # 正常：不加不减
    ("late", 2, "50.00", 1),         # 迟到：每次扣50
    ("early_leave", 2, "50.00", 1),  # 早退：每次扣50
    ("miss_check", 2, "30.00", 1),   # 漏签：每次扣30
    ("absent", 2, "200.00", 1),      # 旷工：每日扣200
    ("leave", 1, "0.00", 0),         # 请假：不动
    ("business_trip", 1, "0.00", 0), # 出差：不动
]

# (parent_name, name, type, path, component, permission_code, sort_order)
ATT_MENUS = [
    ("组织管理", "考勤管理", 2, "/org/attendances", "views/attendance/record/index", "attendance:list", 5),
    ("考勤管理", "手动补录", 3, None, None, "attendance:create", 1),
    ("考勤管理", "导入考勤", 3, None, None, "attendance:import", 2),
    ("组织管理", "考勤规则", 2, "/org/attendance-rules", "views/attendance/rule/index", "attendance_rule:list", 6),
    ("考勤规则", "编辑规则", 3, None, None, "attendance_rule:update", 1),
]

GRANT_ROLE_CODES = ["super_admin", "admin"]

# (code, name, module)
ATT_PERMISSIONS = [
    ("attendance:list", "考勤记录查询", "考勤"),
    ("attendance:create", "手动补录", "考勤"),
    ("attendance:import", "考勤导入", "考勤"),
    ("attendance_rule:list", "考勤规则查询", "考勤"),
    ("attendance_rule:update", "考勤规则编辑", "考勤"),
]

# 菜单名 → 权限码
MENU_PERM_MAP = {
    "考勤管理": "attendance:list",
    "手动补录": "attendance:create",
    "导入考勤": "attendance:import",
    "考勤规则": "attendance_rule:list",
    "编辑规则": "attendance_rule:update",
}

# 考勤状态字典（label ↔ 英文键）
ATT_STATUS_DICT_ITEMS = [
    ("正常", "normal"), ("迟到", "late"), ("早退", "early_leave"),
    ("漏签", "miss_check"), ("旷工", "absent"), ("请假", "leave"), ("出差", "business_trip"),
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
        "att_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("dept_id", sa.BigInteger(), nullable=True),
        sa.Column("att_date", sa.Date(), nullable=False),
        sa.Column("check_in", sa.Time(), nullable=True),
        sa.Column("check_out", sa.Time(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("source", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("importer_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "att_date", name="uk_att_user_date"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_att_user"),
        sa.Index("ix_att_record_date", "att_date"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "att_rule",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("status_key", sa.String(length=16), nullable=False),
        sa.Column("adjust_type", mysql.TINYINT(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("enabled", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("status_key", name="uk_att_rule_status"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )

    # ---------- 2. 预置规则 ----------
    op.bulk_insert(
        sa.table(
            "att_rule",
            sa.column("status_key", sa.String), sa.column("adjust_type", mysql.TINYINT),
            sa.column("amount", sa.Numeric), sa.column("enabled", mysql.TINYINT),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {"status_key": k, "adjust_type": t, "amount": a, "enabled": e, "updated_at": now}
            for k, t, a, e in RULES
        ],
    )

    # ---------- 3. 菜单：考勤管理/考勤规则页面 + 按钮（组织管理下，职位管理之后） ----------
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
            for parent_name, name, mtype, path, component, pcode, sort in ATT_MENUS
        ],
    )
    for parent_name, name, *_ in ATT_MENUS:
        if parent_name not in ("组织管理",):
            bind.execute(
                sa.text("UPDATE sys_menu SET parent_id = :p WHERE id = :i"),
                {"p": _id(bind, "sys_menu", "name", parent_name), "i": _id(bind, "sys_menu", "name", name)},
            )
    for name, sort in [("角色管理", 7), ("菜单管理", 8), ("入职邀请管理", 9)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
        )

    # ---------- 4. 权限码字典 + 菜单-权限关联 ----------
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
            for code, pname, module in ATT_PERMISSIONS
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

    # ---------- 5. 角色授权（超级管理员/普通管理员） ----------
    att_menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in ATT_MENUS]
    op.bulk_insert(
        sa.table(
            "sys_role_menu_relation",
            sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"role_id": _id(bind, "sys_role", "code", role_code), "menu_id": menu_id, "created_at": now}
            for role_code in GRANT_ROLE_CODES
            for menu_id in att_menu_ids
        ],
    )

    # ---------- 6. 考勤状态字典 ----------
    op.bulk_insert(
        sa.table(
            "sys_dict_type",
            sa.column("dict_name", sa.String), sa.column("dict_code", sa.String),
            sa.column("description", sa.String), sa.column("status", mysql.TINYINT),
            sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        ),
        [{"dict_name": "考勤状态", "dict_code": "attendance_status", "description": "考勤记录状态",
          "status": 1, "created_at": now, "updated_at": now}],
    )
    op.bulk_insert(
        sa.table(
            "sys_dict_item",
            sa.column("dict_code", sa.String), sa.column("item_label", sa.String),
            sa.column("item_value", sa.String), sa.column("sort_order", sa.Integer),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {"dict_code": "attendance_status", "item_label": label, "item_value": value,
             "sort_order": i, "status": 1, "created_at": now, "updated_at": now}
            for i, (label, value) in enumerate(ATT_STATUS_DICT_ITEMS)
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in ATT_MENUS]
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
    perm_codes = [code for code, _, _ in ATT_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM sys_permission WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": perm_codes},
    )
    bind.execute(sa.text("DELETE FROM sys_dict_item WHERE dict_code = 'attendance_status'"))
    bind.execute(sa.text("DELETE FROM sys_dict_type WHERE dict_code = 'attendance_status'"))
    for name, sort in [("角色管理", 5), ("菜单管理", 6), ("入职邀请管理", 7)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
        )
    op.drop_table("att_rule")
    op.drop_table("att_record")
