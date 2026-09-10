"""M8 AI 助手长期记忆：新建 ai_memory 表（按用户隔离，提问时向量召回注入 system prompt）。

Revision ID: b0a1c2d3e4f5
Revises: a9b8c7d6e5f4
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "b0a1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 ai_memory：长期记忆事实源（Chroma 仅存向量与定位 id，可从此表重建）。"""
    op.create_table(
        "ai_memory",
        sa.Column("id", mysql.BIGINT(unsigned=False), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("user_id", mysql.BIGINT(unsigned=False), nullable=False, comment="归属用户"),
        sa.Column("content", mysql.VARCHAR(length=300), nullable=False, comment="记忆内容（≤300字）"),
        sa.Column("memory_type", mysql.VARCHAR(length=16), server_default="fact", nullable=False, comment="fact事实/preference偏好"),
        sa.Column("source_conversation_id", mysql.BIGINT(unsigned=False), nullable=True, comment="来源会话（提取自该轮问答）"),
        sa.Column("status", mysql.TINYINT(), server_default="1", nullable=False, comment="1正常 2软删除"),
        sa.Column("created_at", mysql.DATETIME(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", mysql.DATETIME(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"]),
    )
    op.create_index("ix_ai_memory_user_status", "ai_memory", ["user_id", "status"])


def downgrade() -> None:
    """回滚：删除 ai_memory 表。"""
    op.drop_index("ix_ai_memory_user_status", table_name="ai_memory")
    op.drop_table("ai_memory")
