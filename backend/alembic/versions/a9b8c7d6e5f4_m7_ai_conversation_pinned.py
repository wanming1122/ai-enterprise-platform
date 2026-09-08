"""M7 会话管理：ai_conversation 增加 pinned 置顶标记（AI助手会话置顶能力）。

Revision ID: a9b8c7d6e5f4
Revises: f8a7b6c5d4e3
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "f8a7b6c5d4e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 pinned 列：1 置顶 0 普通，默认 0。"""
    op.add_column(
        "ai_conversation",
        sa.Column("pinned", mysql.TINYINT(), server_default="0", nullable=False, comment="1置顶 0普通（列表置顶优先）"),
    )


def downgrade() -> None:
    """回滚：删除 pinned 列。"""
    op.drop_column("ai_conversation", "pinned")
