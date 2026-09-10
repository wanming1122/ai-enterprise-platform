"""M10 AI 助手用量监控：ai_message 增加 usage 统计列（随 assistant 终答落库，供成本聚合）。

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_message", sa.Column("usage", sa.JSON(), nullable=True, comment="本轮用量统计（tokens/耗时/模型）"))


def downgrade() -> None:
    op.drop_column("ai_message", "usage")
