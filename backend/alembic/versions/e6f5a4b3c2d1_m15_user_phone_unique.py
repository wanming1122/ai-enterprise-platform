"""M15 用户手机号唯一性约束。

背景：员工手机号应全局唯一。此前 sys_user.phone 无唯一索引，应用层也未做
查重，并发写入会落重复数据。本迁移：
1. 释放软删行（status=2）占用的手机号（软删账号不应继续占用全局唯一手机号，
   与删除用户时释放用户名唯一键同一思路）；
2. 检测在职/停用账号中的重复手机号，存在则中止迁移（避免静默丢数据，提示人工处理）；
3. 为 sys_user.phone 建唯一索引 uk_user_phone（MySQL 唯一索引允许多个 NULL）。

Revision ID: e6f5a4b3c2d1
Revises: c2b3d4e5f6a7
Create Date: 2026-09-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e6f5a4b3c2d1"
down_revision: str = "c2b3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 软删行释放手机号：软删账号不再占用全局唯一手机号
    bind.execute(
        sa.text("UPDATE sys_user SET phone = NULL WHERE status = 2 AND phone IS NOT NULL")
    )

    # 2) 在职/停用账号中的重复手机号：存在则中止，交由人工处理（保留数据完整性）
    dups = bind.execute(
        sa.text(
            "SELECT phone, COUNT(*) AS c FROM sys_user "
            "WHERE status != 2 AND phone IS NOT NULL AND phone <> '' "
            "GROUP BY phone HAVING c > 1"
        )
    ).fetchall()
    if dups:
        raise RuntimeError(f"存在重复手机号，请先人工处理后再升级: {dups}")

    # 3) 唯一索引兜底并发写入
    op.create_index("uk_user_phone", "sys_user", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("uk_user_phone", table_name="sys_user")
