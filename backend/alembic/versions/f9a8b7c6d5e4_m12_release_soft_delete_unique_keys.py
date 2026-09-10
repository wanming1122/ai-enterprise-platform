"""M12 数据修复：释放软删行占用的唯一键。

背景：全局约定软删除（status=2），但软删行仍占用物理唯一索引，
导致同名/同编码实体删除后无法重建（报"已存在"或唯一约束冲突）。
本次统一：删除时改写唯一字段（代码层已修复），并对历史存量软删数据做一次性释放。

涉及唯一索引：
- sys_user.uk_user_username
- sys_position.uk_position_name / uk_position_code
- kb_knowledge_base.uk_kb_name
- sys_dict_type.uk_dict_code
- kb_file.uk_kbfile_hash（kb_id + content_hash，哈希列宽 64，改用 deleted_{id}_{前40位}）

Revision ID: f9a8b7c6d5e4
Revises: e1f2a3b4c5d6
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9a8b7c6d5e4"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 幂等：LOCATE 字面匹配，已改名的行不会重复处理；长度按列宽安全截断
_UPGRADE_SQL = [
    # sys_user.username varchar(64)（审批驳回已用 #rejected{id}，此处用 #deleted{id}）
    """
    UPDATE sys_user
    SET username = CONCAT(LEFT(username, 64 - CHAR_LENGTH(CONCAT('#deleted', id))), '#deleted', id)
    WHERE status = 2
      AND LOCATE('#deleted', username) = 0
      AND LOCATE('#rejected', username) = 0
    """,
    # sys_position.name varchar(64) / code varchar(32)
    """
    UPDATE sys_position
    SET name = CONCAT(LEFT(name, 64 - CHAR_LENGTH(CONCAT('_deleted_', id))), '_deleted_', id),
        code = CONCAT(LEFT(code, 32 - CHAR_LENGTH(CONCAT('_deleted_', id))), '_deleted_', id)
    WHERE status = 2 AND LOCATE('_deleted_', name) = 0
    """,
    # kb_knowledge_base.name varchar(64)
    """
    UPDATE kb_knowledge_base
    SET name = CONCAT(LEFT(name, 64 - CHAR_LENGTH(CONCAT('_deleted_', id))), '_deleted_', id)
    WHERE status = 2 AND LOCATE('_deleted_', name) = 0
    """,
    # sys_dict_type.dict_code varchar(64)
    """
    UPDATE sys_dict_type
    SET dict_code = CONCAT(LEFT(dict_code, 64 - CHAR_LENGTH(CONCAT('_deleted_', id))), '_deleted_', id)
    WHERE status = 2 AND LOCATE('_deleted_', dict_code) = 0
    """,
    # kb_file.content_hash varchar(64)：恰为 SHA256 长度，无法追加后缀
    """
    UPDATE kb_file
    SET content_hash = CONCAT('deleted_', id, '_', LEFT(content_hash, 40))
    WHERE status = 2 AND LOCATE('deleted_', content_hash) = 0
    """,
]


def upgrade() -> None:
    """释放存量软删行占用的唯一键（幂等，可重复执行）。"""
    bind = op.get_bind()
    for sql in _UPGRADE_SQL:
        bind.execute(sa.text(sql))


def downgrade() -> None:
    """数据修复不可逆：原值已被改写，无法还原（保留 pass）。"""
    pass
