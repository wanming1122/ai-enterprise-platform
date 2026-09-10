"""M13 入职邀请：被邀请人姓名改为可空（选填）。

背景：新建邀请弹窗将被邀请人姓名由必填改为选填，需放开 sys_invitation.name 的
NOT NULL 约束以与后端 Schema（name: str | None）保持一致。

Revision ID: b1a2c3d4e5f6
Revises: f9a8b7c6d5e4
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f9a8b7c6d5e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """sys_invitation.name 放开为可空（被邀请人姓名选填）。"""
    op.alter_column(
        "sys_invitation",
        "name",
        existing_type=sa.String(length=64),
        nullable=True,
        existing_comment="被邀请人姓名",
        comment="被邀请人姓名（选填）",
    )


def downgrade() -> None:
    """回滚为 NOT NULL：先把 NULL 归一为空串，避免降级失败。"""
    op.execute("UPDATE sys_invitation SET name = '' WHERE name IS NULL")
    op.alter_column(
        "sys_invitation",
        "name",
        existing_type=sa.String(length=64),
        nullable=False,
        existing_comment="被邀请人姓名（选填）",
        comment="被邀请人姓名",
    )
