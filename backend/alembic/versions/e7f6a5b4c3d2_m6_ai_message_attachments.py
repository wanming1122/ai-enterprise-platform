"""M6-T2 AI助手多模态：ai_message 补 attachments JSON 列（用户上传图片 Data URL 列表）。

Revision ID: e7f6a5b4c3d2
Revises: d2e3f4a5b6c7
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f6a5b4c3d2"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ai_message",
        sa.Column("attachments", sa.JSON(), nullable=True, comment="附件列表（多模态图片 Data URL）"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ai_message", "attachments")
