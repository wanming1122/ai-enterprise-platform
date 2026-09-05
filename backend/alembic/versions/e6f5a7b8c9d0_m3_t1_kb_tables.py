"""M3-T1 RAG知识库一期：kb三张表、AI智能中心菜单与权限码。

Revision ID: e6f5a7b8c9d0
Revises: d5e4f6a7b8c9
Create Date: 2026-09-05

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "e6f5a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d5e4f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (parent_name, name, type, path, component, icon, permission_code, sort_order)
KB_MENUS = [
    (None, "AI智能中心", 1, "/ai", None, "RobotOutlined", None, 3),
    ("AI智能中心", "知识库管理", 2, "/ai/kb", "views/ai/kb/index", None, "kb:list", 1),
    ("知识库管理", "新建知识库", 3, None, None, None, "kb:create", 1),
    ("知识库管理", "编辑知识库", 3, None, None, None, "kb:update", 2),
    ("知识库管理", "删除知识库", 3, None, None, None, "kb:delete", 3),
    ("知识库管理", "上传文件", 3, None, None, None, "file:upload", 4),
    ("知识库管理", "文件查看", 3, None, None, None, "file:list", 5),
    ("知识库管理", "重新解析", 3, None, None, None, "file:reparse", 6),
    ("知识库管理", "删除文件", 3, None, None, None, "file:delete", 7),
    ("AI智能中心", "问答调试", 2, "/ai/kb/chat", "views/ai/kb/chat/index", None, "kb:chat", 2),
    ("问答调试", "检索调试", 3, None, None, None, "kb:search", 1),
]

GRANT_ROLE_CODES = ["super_admin", "admin"]

# (code, name, module)
KB_PERMISSIONS = [
    ("kb:list", "知识库查询", "知识库"),
    ("kb:create", "新建知识库", "知识库"),
    ("kb:update", "编辑知识库", "知识库"),
    ("kb:delete", "删除知识库", "知识库"),
    ("file:upload", "上传文件", "知识库"),
    ("file:list", "文件查看", "知识库"),
    ("file:reparse", "重新解析", "知识库"),
    ("file:delete", "删除文件", "知识库"),
    ("kb:chat", "知识库问答", "知识库"),
    ("kb:search", "检索调试", "知识库"),
]

MENU_PERM_MAP = {
    "AI智能中心": None,
    "知识库管理": "kb:list",
    "新建知识库": "kb:create",
    "编辑知识库": "kb:update",
    "删除知识库": "kb:delete",
    "上传文件": "file:upload",
    "文件查看": "file:list",
    "重新解析": "file:reparse",
    "删除文件": "file:delete",
    "问答调试": "kb:chat",
    "检索调试": "kb:search",
}


def _id(bind, table: str, field: str, value) -> int:
    return bind.execute(
        sa.text(f"SELECT id FROM {table} WHERE {field} = :v"), {"v": value}
    ).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    now = datetime.now()
    bind = op.get_bind()

    # ---------- 1. 建表 ----------
    op.create_table(
        "kb_knowledge_base",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("embedding_model", sa.String(length=64), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=True, server_default="500"),
        sa.Column("chunk_overlap", sa.Integer(), nullable=True, server_default="80"),
        sa.Column("collection_name", sa.String(length=64), nullable=False),
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("creator_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uk_kb_name"),
        sa.ForeignKeyConstraint(["creator_id"], ["sys_user.id"], name="fk_kb_creator"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "kb_file",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=255), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("parse_status", mysql.TINYINT(), nullable=True, server_default="0"),
        sa.Column("fail_reason", sa.String(length=255), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("uploader_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kb_id", "content_hash", name="uk_kbfile_hash"),
        sa.ForeignKeyConstraint(["kb_id"], ["kb_knowledge_base.id"], name="fk_kbfile_kb"),
        sa.ForeignKeyConstraint(["uploader_id"], ["sys_user.id"], name="fk_kbfile_uploader"),
        sa.Index("ix_kbfile_kb_status", "kb_id", "status"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "kb_chunk",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column("title_path", sa.String(length=255), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("chunk_type", sa.String(length=16), nullable=True, server_default="text"),
        sa.Column("status", mysql.TINYINT(), nullable=True, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["file_id"], ["kb_file.id"], name="fk_kbchunk_file"),
        sa.Index("ix_kbchunk_file", "file_id"),
        sa.Index("ix_kbchunk_kb_status", "kb_id", "status"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )

    # ---------- 2. 菜单：AI智能中心目录 + 页面 + 按钮 ----------
    op.bulk_insert(
        sa.table(
            "sys_menu",
            sa.column("parent_id", sa.BigInteger), sa.column("name", sa.String),
            sa.column("type", mysql.TINYINT), sa.column("path", sa.String),
            sa.column("component", sa.String), sa.column("icon", sa.String),
            sa.column("permission_code", sa.String), sa.column("visible", mysql.TINYINT),
            sa.column("is_external", mysql.TINYINT), sa.column("sort_order", sa.Integer),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "parent_id": None, "name": name, "type": mtype, "path": path,
                "component": component, "icon": icon, "permission_code": pcode,
                "visible": 1, "is_external": 0, "sort_order": sort, "status": 1,
                "created_at": now, "updated_at": now,
            }
            for _, name, mtype, path, component, icon, pcode, sort in KB_MENUS
        ],
    )
    for parent_name, name, *_ in KB_MENUS:
        if parent_name is not None:
            bind.execute(
                sa.text("UPDATE sys_menu SET parent_id = :p WHERE id = :i"),
                {"p": _id(bind, "sys_menu", "name", parent_name), "i": _id(bind, "sys_menu", "name", name)},
            )
    for name, sort in [("操作日志", 4), ("系统配置", 5), ("个人中心", 6)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
        )

    # ---------- 3. 权限码字典 + 菜单-权限关联 ----------
    op.bulk_insert(
        sa.table(
            "sys_permission",
            sa.column("name", sa.String), sa.column("code", sa.String),
            sa.column("module", sa.String), sa.column("description", sa.String),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {"name": pname, "code": code, "module": module, "description": pname,
             "status": 1, "created_at": now, "updated_at": now}
            for code, pname, module in KB_PERMISSIONS
        ],
    )
    op.bulk_insert(
        sa.table(
            "sys_menu_permission_relation",
            sa.column("menu_id", sa.BigInteger), sa.column("permission_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"menu_id": _id(bind, "sys_menu", "name", menu_name),
             "permission_id": _id(bind, "sys_permission", "code", code),
             "created_at": now}
            for menu_name, code in MENU_PERM_MAP.items() if code
        ],
    )

    # ---------- 4. 角色授权（超级管理员/普通管理员） ----------
    kb_menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in KB_MENUS]
    op.bulk_insert(
        sa.table(
            "sys_role_menu_relation",
            sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {"role_id": _id(bind, "sys_role", "code", role_code), "menu_id": menu_id, "created_at": now}
            for role_code in GRANT_ROLE_CODES
            for menu_id in kb_menu_ids
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    menu_ids = [_id(bind, "sys_menu", "name", n) for _, n, *_ in KB_MENUS]
    bind.execute(
        sa.text("DELETE FROM sys_role_menu_relation WHERE menu_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": menu_ids},
    )
    bind.execute(
        sa.text("DELETE FROM sys_menu_permission_relation WHERE menu_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": menu_ids},
    )
    bind.execute(sa.text("DELETE FROM sys_menu WHERE id IN :ids").bindparams(
        sa.bindparam("ids", expanding=True)
    ), {"ids": menu_ids})
    perm_codes = [code for code, _, _ in KB_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM sys_permission WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": perm_codes},
    )
    for name, sort in [("操作日志", 3), ("系统配置", 4), ("个人中心", 5)]:
        bind.execute(
            sa.text("UPDATE sys_menu SET sort_order = :s WHERE name = :n"), {"s": sort, "n": name}
        )
    op.drop_table("kb_chunk")
    op.drop_table("kb_file")
    op.drop_table("kb_knowledge_base")
