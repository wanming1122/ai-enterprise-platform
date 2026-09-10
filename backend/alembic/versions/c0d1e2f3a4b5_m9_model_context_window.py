"""M9 模型配置增加 context_window 上下文窗口字段（AI 助手容量圆环按所选模型真实窗口计算）。

Revision ID: c0d1e2f3a4b5
Revises: b0a1c2d3e4f5
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b0a1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 context_window 列：可空（空则回退全局常量 CONTEXT_WINDOW_TOKENS）。"""
    op.add_column(
        "ai_model",
        sa.Column("context_window", sa.Integer(), nullable=True, comment="上下文窗口（token，仅 llm；空则用全局常量）"),
    )


def downgrade() -> None:
    """回滚：删除 context_window 列。"""
    op.drop_column("ai_model", "context_window")
