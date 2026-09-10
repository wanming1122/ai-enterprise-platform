"""M14 修复「问答调试」菜单权限码与页面实际调用链路不一致。

背景：问答调试页（views/ai/kb/chat/index.tsx）已复用 AI 助手链路
（GET /ai/conversations*、POST /ai/chat，均要求 ai:chat），并需拉取知识库列表
（GET /kb/bases，要求 kb:list）；但菜单种子里「问答调试」的权限码与菜单-权限关联
仍是 kb:chat，导致仅被授予「问答调试」(kb:chat) 而未授予「AI助手」(ai:chat) 的角色
进入页面后接口全部 403，且 kb:chat 形同虚设。

本迁移把该菜单权限对齐到页面真实需要：
- sys_menu.permission_code：kb:chat → ai:chat
- sys_menu_permission_relation：移除 kb:chat，补 ai:chat 与 kb:list

Revision ID: c2b3d4e5f6a7
Revises: b1a2c3d4e5f6
Create Date: 2026-09-10

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2b3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "b1a2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MENU_NAME = "问答调试"
MENU_PERM_OLD = "kb:chat"   # 原菜单权限码（已失效）
MENU_PERM_NEW = "ai:chat"   # 页面问答/会话接口所需
EXTRA_REL_PERM = "kb:list"  # 页面选库接口 GET /kb/bases 所需


def _scalar(bind, sql: str, **params):
    return bind.execute(sa.text(sql), params).scalar()


def _menu_id(bind) -> int | None:
    return _scalar(bind, "SELECT id FROM sys_menu WHERE name = :n", n=MENU_NAME)


def _perm_id(bind, code: str) -> int | None:
    return _scalar(bind, "SELECT id FROM sys_permission WHERE code = :c", c=code)


def _bind_perm(bind, menu_id: int, perm_id: int) -> None:
    """建立菜单-权限关联（已存在则跳过）。"""
    exists = _scalar(
        bind,
        "SELECT 1 FROM sys_menu_permission_relation WHERE menu_id = :m AND permission_id = :p",
        m=menu_id, p=perm_id,
    )
    if exists is None:
        bind.execute(
            sa.text(
                "INSERT INTO sys_menu_permission_relation (menu_id, permission_id, created_at) "
                "VALUES (:m, :p, :t)"
            ),
            {"m": menu_id, "p": perm_id, "t": datetime.now()},
        )


def _unbind_perm(bind, menu_id: int, perm_id: int) -> None:
    bind.execute(
        sa.text(
            "DELETE FROM sys_menu_permission_relation WHERE menu_id = :m AND permission_id = :p"
        ),
        {"m": menu_id, "p": perm_id},
    )


def upgrade() -> None:
    """菜单权限对齐页面真实调用：kb:chat → ai:chat（并补 kb:list）。"""
    bind = op.get_bind()
    menu_id = _menu_id(bind)
    if menu_id is None:
        return

    # 1) 页面菜单权限码指向 ai:chat
    bind.execute(
        sa.text("UPDATE sys_menu SET permission_code = :c WHERE id = :m"),
        {"c": MENU_PERM_NEW, "m": menu_id},
    )

    # 2) 菜单-权限关联：移除 kb:chat，补 ai:chat 与 kb:list
    old_id = _perm_id(bind, MENU_PERM_OLD)
    if old_id is not None:
        _unbind_perm(bind, menu_id, old_id)
    for code in (MENU_PERM_NEW, EXTRA_REL_PERM):
        pid = _perm_id(bind, code)
        if pid is not None:
            _bind_perm(bind, menu_id, pid)


def downgrade() -> None:
    """还原为 kb:chat。"""
    bind = op.get_bind()
    menu_id = _menu_id(bind)
    if menu_id is None:
        return

    bind.execute(
        sa.text("UPDATE sys_menu SET permission_code = :c WHERE id = :m"),
        {"c": MENU_PERM_OLD, "m": menu_id},
    )
    for code in (MENU_PERM_NEW, EXTRA_REL_PERM):
        pid = _perm_id(bind, code)
        if pid is not None:
            _unbind_perm(bind, menu_id, pid)
    old_id = _perm_id(bind, MENU_PERM_OLD)
    if old_id is not None:
        _bind_perm(bind, menu_id, old_id)
