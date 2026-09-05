"""M3-T3 会话表（复用 AI 智能中心会话体系，M4 AI助手共用）。

Revision ID: f7a6b8c9d0e1
Revises: e6f5a7b8c9d0
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "f7a6b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e6f5a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ai_conversation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_conv_user"),
        sa.Index("ix_conv_user", "user_id"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "ai_message",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, comment="user/assistant/tool"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(length=32), nullable=True),
        sa.Column("citations", mysql.JSON(), nullable=True, comment="引用来源列表"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversation.id"], name="fk_msg_conv"),
        sa.Index("ix_msg_conv", "conversation_id"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("ai_message")
    op.drop_table("ai_conversation")
