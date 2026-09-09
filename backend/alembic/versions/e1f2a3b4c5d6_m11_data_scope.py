"""M11 数据范围权限：sys_role 增加 data_scope 字段，支持按角色控制数据可见范围。

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. sys_role表增加data_scope字段，默认值3（全部）保证向后兼容
    op.add_column("sys_role", sa.Column(
        "data_scope",
        mysql.TINYINT(),
        nullable=False,
        server_default="3",
        comment="数据范围: 1仅本人 2本部门 3全部"
    ))

    # 2. 超级管理员角色强制设为全部数据范围
    op.execute("UPDATE sys_role SET data_scope = 3 WHERE role_type = 1")


def downgrade() -> None:
    op.drop_column("sys_role", "data_scope")
