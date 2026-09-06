"""M5 边界修复：employee 角色补授 AI助手入口（AI智能中心目录 + AI助手页面菜单授权）。

Revision ID: d2e3f4a5b6c7
Revises: c0d9e8f7a6b5
Create Date: 2026-09-06

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c0d9e8f7a6b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 授予 employee 角色的菜单（含父目录，保证侧边栏正常分组）
GRANT_MENU_KEYS = [("AI智能中心", 1), ("AI助手", 2)]  # (菜单名, 类型)
GRANT_ROLE_CODES = ["employee"]


def _menu_id(bind, name: str, mtype: int) -> int:
    return bind.execute(
        sa.text("SELECT id FROM sys_menu WHERE name = :n AND type = :t"),
        {"n": name, "t": mtype},
    ).scalar_one()


def _role_id(bind, code: str) -> int:
    return bind.execute(
        sa.text("SELECT id FROM sys_role WHERE code = :c"), {"c": code}
    ).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    now = datetime.now()
    bind = op.get_bind()
    menu_ids = [_menu_id(bind, n, t) for n, t in GRANT_MENU_KEYS]
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
    menu_ids = [_menu_id(bind, n, t) for n, t in GRANT_MENU_KEYS]
    role_ids = [_role_id(bind, c) for c in GRANT_ROLE_CODES]
    bind.execute(
        sa.text(
            "DELETE FROM sys_role_menu_relation "
            "WHERE role_id IN :rids AND menu_id IN :mids"
        ).bindparams(sa.bindparam("rids", expanding=True), sa.bindparam("mids", expanding=True)),
        {"rids": role_ids, "mids": menu_ids},
    )
