"""M1-T1: 组织与权限表迁移（16 张 sys_* 表 + 预置数据）

Revision ID: a1f2e3d4c5b6
Revises: 2248fab53386
Create Date: 2026-09-04

说明：
- 按《组织架构模块设计方案》第四章创建全部 sys_* 表。
- sys_department.leader_id 与 sys_user.department_id 互为外键形成环，建表阶段
  先以普通列创建 sys_department，待 sys_user 建好后通过 ALTER 补充外键。
- 预置数据随迁移写入：超级管理员、六个预置部门、基础角色、完整菜单树与权限标识字典。
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a1f2e3d4c5b6"
down_revision = "2248fab53386"
branch_labels = None
depends_on = None


def _now() -> datetime:
    return datetime.now()


def _id(bind, table: str, col: str, value) -> int | None:
    """按唯一列取值查询主键 ID。"""
    return bind.execute(
        sa.text(f"SELECT id FROM {table} WHERE {col} = :v"), {"v": value}
    ).scalar()


# ---------- 预置数据定义 ----------

ADMIN_PASSWORD_HASH = "$2b$12$MMYU9MN7abvgbyq98iRyV.Z0qhqO2j/bwrRf6JdtZ7zMC3F9F52Lm"

DEPARTMENTS = ["技术部", "销售部", "人事行政", "产品", "后勤采购", "财务"]

ROLES = [
    {"name": "超级管理员", "code": "super_admin", "role_type": 1, "description": "拥有全部菜单与按钮权限"},
    {"name": "普通管理员", "code": "admin", "role_type": 2, "description": "组织管理/操作日志/系统配置"},
    {"name": "普通员工", "code": "employee", "role_type": 3, "description": "工作台与个人中心"},
]

# (parent_name, name, type, path, component, icon, permission_code, sort_order)
MENUS = [
    (None, "工作台", 2, "/dashboard", "views/dashboard/index", "DashboardOutlined", "dashboard:view", 1),
    (None, "组织管理", 1, "/org", None, "ApartmentOutlined", None, 2),
    ("组织管理", "用户管理", 2, "/org/users", "views/org/user/index", None, "user:list", 1),
    ("用户管理", "新增用户", 3, None, None, None, "user:create", 1),
    ("用户管理", "编辑用户", 3, None, None, None, "user:update", 2),
    ("用户管理", "删除用户", 3, None, None, None, "user:delete", 3),
    ("用户管理", "启停账号", 3, None, None, None, "user:toggle", 4),
    ("用户管理", "重置密码", 3, None, None, None, "user:reset_pwd", 5),
    ("用户管理", "导入用户", 3, None, None, None, "user:import", 6),
    ("用户管理", "导出用户", 3, None, None, None, "user:export", 7),
    ("组织管理", "注册审批", 2, "/org/approvals", "views/org/approval/index", None, "approval:list", 2),
    ("注册审批", "审批通过", 3, None, None, None, "approval:approve", 1),
    ("注册审批", "审批驳回", 3, None, None, None, "approval:reject", 2),
    ("组织管理", "部门管理", 2, "/org/departments", "views/org/department/index", None, "dept:list", 3),
    ("部门管理", "新增部门", 3, None, None, None, "dept:create", 1),
    ("部门管理", "编辑部门", 3, None, None, None, "dept:update", 2),
    ("部门管理", "删除部门", 3, None, None, None, "dept:delete", 3),
    ("部门管理", "启停部门", 3, None, None, None, "dept:toggle", 4),
    ("部门管理", "部门排序", 3, None, None, None, "dept:sort", 5),
    ("组织管理", "角色管理", 2, "/org/roles", "views/org/role/index", None, "role:list", 4),
    ("角色管理", "新增角色", 3, None, None, None, "role:create", 1),
    ("角色管理", "编辑角色", 3, None, None, None, "role:update", 2),
    ("角色管理", "删除角色", 3, None, None, None, "role:delete", 3),
    ("角色管理", "菜单授权", 3, None, None, None, "role:authorize", 4),
    ("组织管理", "菜单管理", 2, "/org/menus", "views/org/menu/index", None, "menu:list", 5),
    ("菜单管理", "新增菜单", 3, None, None, None, "menu:create", 1),
    ("菜单管理", "编辑菜单", 3, None, None, None, "menu:update", 2),
    ("菜单管理", "删除菜单", 3, None, None, None, "menu:delete", 3),
    ("菜单管理", "启停菜单", 3, None, None, None, "menu:toggle", 4),
    ("菜单管理", "菜单排序", 3, None, None, None, "menu:sort", 5),
    ("组织管理", "入职邀请管理", 2, "/org/invitations", "views/org/invitation/index", None, "invitation:list", 6),
    ("入职邀请管理", "新建邀请", 3, None, None, None, "invitation:create", 1),
    ("入职邀请管理", "重发邀请", 3, None, None, None, "invitation:resend", 2),
    ("入职邀请管理", "撤销邀请", 3, None, None, None, "invitation:revoke", 3),
    ("入职邀请管理", "删除邀请", 3, None, None, None, "invitation:delete", 4),
    (None, "操作日志", 2, "/logs", "views/log/index", "FileTextOutlined", "log:list", 3),
    (None, "系统配置", 1, "/settings", None, "SettingOutlined", None, 4),
    ("系统配置", "参数配置", 2, "/settings/config", "views/settings/config/index", None, "config:list", 1),
    ("参数配置", "更新配置", 3, None, None, None, "config:update", 1),
    ("系统配置", "字典管理", 2, "/settings/dicts", "views/settings/dict/index", None, "dict:list", 2),
    ("字典管理", "新增字典", 3, None, None, None, "dict:create", 1),
    ("字典管理", "编辑字典", 3, None, None, None, "dict:update", 2),
    ("字典管理", "删除字典", 3, None, None, None, "dict:delete", 3),
    (None, "个人中心", 1, "/profile", None, "UserOutlined", None, 5),
    ("个人中心", "我的信息", 2, "/profile/info", "views/profile/info/index", None, "profile:view", 1),
    ("个人中心", "我的工资", 2, "/profile/salary", "views/profile/salary/index", None, "salary:view", 2),
    ("个人中心", "我的考勤", 2, "/profile/attendance", "views/profile/attendance/index", None, "attendance:view", 3),
]

# (code, name, module)
PERMISSIONS = [
    ("dashboard:view", "工作台查看", "工作台"),
    ("user:list", "用户列表查询", "用户"),
    ("user:create", "新增用户", "用户"),
    ("user:update", "编辑用户", "用户"),
    ("user:delete", "删除用户", "用户"),
    ("user:toggle", "账号启停", "用户"),
    ("user:reset_pwd", "重置密码", "用户"),
    ("user:import", "批量导入", "用户"),
    ("user:export", "批量导出", "用户"),
    ("approval:list", "审批列表查询", "注册审批"),
    ("approval:approve", "审批通过", "注册审批"),
    ("approval:reject", "审批驳回", "注册审批"),
    ("dept:list", "部门列表查询", "部门"),
    ("dept:create", "新增部门", "部门"),
    ("dept:update", "编辑部门", "部门"),
    ("dept:delete", "删除部门", "部门"),
    ("dept:toggle", "部门启停", "部门"),
    ("dept:sort", "部门排序", "部门"),
    ("role:list", "角色列表查询", "角色"),
    ("role:create", "新增角色", "角色"),
    ("role:update", "编辑角色", "角色"),
    ("role:delete", "删除角色", "角色"),
    ("role:authorize", "菜单授权", "角色"),
    ("menu:list", "菜单列表查询", "菜单"),
    ("menu:create", "新增菜单", "菜单"),
    ("menu:update", "编辑菜单", "菜单"),
    ("menu:delete", "删除菜单", "菜单"),
    ("menu:toggle", "菜单启停", "菜单"),
    ("menu:sort", "菜单排序", "菜单"),
    ("invitation:list", "邀请列表查询", "入职邀请"),
    ("invitation:create", "新建邀请", "入职邀请"),
    ("invitation:resend", "重发邀请", "入职邀请"),
    ("invitation:revoke", "撤销邀请", "入职邀请"),
    ("invitation:delete", "删除邀请", "入职邀请"),
    ("log:list", "日志查询", "操作日志"),
    ("config:list", "配置查询", "系统配置"),
    ("config:update", "更新配置", "系统配置"),
    ("dict:list", "字典查询", "字典管理"),
    ("dict:create", "新增字典", "字典管理"),
    ("dict:update", "编辑字典", "字典管理"),
    ("dict:delete", "删除字典", "字典管理"),
    ("profile:view", "查看个人信息", "个人中心"),
    ("salary:view", "查看我的工资", "个人中心"),
    ("attendance:view", "查看我的考勤", "个人中心"),
]

# 各角色授权菜单名集合
ROLE_MENU_NAMES = {
    "super_admin": None,  # 全部
    "admin": {
        "组织管理", "用户管理", "新增用户", "编辑用户", "删除用户", "启停账号", "重置密码", "导入用户", "导出用户",
        "注册审批", "审批通过", "审批驳回",
        "部门管理", "新增部门", "编辑部门", "删除部门", "启停部门", "部门排序",
        "角色管理", "新增角色", "编辑角色", "删除角色", "菜单授权",
        "菜单管理", "新增菜单", "编辑菜单", "删除菜单", "启停菜单", "菜单排序",
        "入职邀请管理", "新建邀请", "重发邀请", "撤销邀请", "删除邀请",
        "操作日志",
        "系统配置", "参数配置", "更新配置", "字典管理", "新增字典", "编辑字典", "删除字典",
    },
    "employee": {"工作台", "个人中心", "我的信息", "我的工资", "我的考勤"},
}

# dict_code: (dict_name, [(item_label, item_value), ...])
DICTS = {
    "user_status": ("用户状态", [("正常", "1"), ("停用", "0"), ("删除", "2")]),
    "gender": ("性别", [("未知", "0"), ("男", "1"), ("女", "2")]),
    "menu_type": ("菜单类型", [("目录", "1"), ("页面", "2"), ("按钮", "3")]),
    "invite_status": (
        "邀请状态",
        [("待发送", "0"), ("已发送", "1"), ("已打开", "2"), ("已注册", "3"), ("已过期", "4"), ("已撤销", "5"), ("处理失败", "6")],
    ),
    "approval_status": ("审批状态", [("待审批", "0"), ("通过", "1"), ("驳回", "2")]),
}


def upgrade() -> None:
    """Upgrade schema."""
    # ---------- 1. 建表 ----------
    op.create_table(
        "sys_department",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("leader_id", sa.BigInteger(), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["sys_department.id"], name="fk_dept_parent"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=64), nullable=True),
        sa.Column("real_name", sa.String(length=64), nullable=True),
        sa.Column("gender", mysql.TINYINT(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("social_account", sa.String(length=128), nullable=True),
        sa.Column("department_id", sa.BigInteger(), nullable=True),
        sa.Column("post", sa.String(length=64), nullable=True),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("need_reset_pwd", mysql.TINYINT(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_login_ip", sa.String(length=64), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uk_user_username"),
        sa.ForeignKeyConstraint(["department_id"], ["sys_department.id"], name="fk_user_department"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    # 补充环中外键：sys_department.leader_id -> sys_user.id
    op.create_foreign_key("fk_department_leader", "sys_department", "sys_user", ["leader_id"], ["id"])

    op.create_table(
        "sys_role",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("role_type", mysql.TINYINT(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uk_role_name"),
        sa.UniqueConstraint("code", name="uk_role_code"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_user_role_relation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uk_user_role"),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"], name="fk_user_role_role"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_user_role_user"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_menu",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("type", mysql.TINYINT(), nullable=True),
        sa.Column("path", sa.String(length=255), nullable=True),
        sa.Column("component", sa.String(length=255), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("permission_code", sa.String(length=64), nullable=True),
        sa.Column("visible", mysql.TINYINT(), nullable=True),
        sa.Column("is_external", mysql.TINYINT(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["sys_menu.id"], name="fk_menu_parent"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_role_menu_relation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("menu_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "menu_id", name="uk_role_menu"),
        sa.ForeignKeyConstraint(["menu_id"], ["sys_menu.id"], name="fk_role_menu_menu"),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"], name="fk_role_menu_role"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_permission",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_permission_code"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_menu_permission_relation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("menu_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("menu_id", "permission_id", name="uk_menu_permission"),
        sa.ForeignKeyConstraint(["menu_id"], ["sys_menu.id"], name="fk_menu_perm_menu"),
        sa.ForeignKeyConstraint(["permission_id"], ["sys_permission.id"], name="fk_menu_perm_perm"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_registration_approval",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("real_name", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("apply_role_id", sa.BigInteger(), nullable=False),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("apply_comment", sa.String(length=255), nullable=True),
        sa.Column("review_comment", sa.String(length=255), nullable=True),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["apply_role_id"], ["sys_role.id"], name="fk_approval_role"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["sys_user.id"], name="fk_approval_reviewer"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_approval_user"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_invitation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("department_id", sa.BigInteger(), nullable=True),
        sa.Column("role_id", sa.BigInteger(), nullable=True),
        sa.Column("post", sa.String(length=64), nullable=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("invite_link", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uk_invitation_token"),
        sa.ForeignKeyConstraint(["department_id"], ["sys_department.id"], name="fk_invitation_dept"),
        sa.ForeignKeyConstraint(["operator_id"], ["sys_user.id"], name="fk_invitation_operator"),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"], name="fk_invitation_role"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_invitation_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invitation_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["invitation_id"], ["sys_invitation.id"], name="fk_inv_log_inv"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_password_recovery_code",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("try_count", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_used", mysql.TINYINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_recovery_user"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("module", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=True),
        sa.Column("path", sa.String(length=255), nullable=True),
        sa.Column("params", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("device", sa.String(length=128), nullable=True),
        sa.Column("result", mysql.TINYINT(), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_log_user"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(length=64), nullable=False),
        sa.Column("config_name", sa.String(length=64), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_key", name="uk_config_key"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_dict_type",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("dict_name", sa.String(length=64), nullable=False),
        sa.Column("dict_code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dict_code", name="uk_dict_code"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        "sys_dict_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("dict_code", sa.String(length=64), nullable=False),
        sa.Column("item_label", sa.String(length=64), nullable=False),
        sa.Column("item_value", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("status", mysql.TINYINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )

    # ---------- 2. 预置数据 ----------
    bind = op.get_bind()
    now = _now()

    # 角色
    op.bulk_insert(
        sa.table(
            "sys_role",
            sa.column("name", sa.String), sa.column("code", sa.String),
            sa.column("role_type", mysql.TINYINT), sa.column("description", sa.String),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {**r, "status": 1, "created_at": now, "updated_at": now}
            for r in ROLES
        ],
    )

    # 六个预置部门
    op.bulk_insert(
        sa.table(
            "sys_department",
            sa.column("name", sa.String), sa.column("parent_id", sa.BigInteger),
            sa.column("leader_id", sa.BigInteger), sa.column("sort_order", sa.Integer),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "name": name, "parent_id": None, "leader_id": None,
                "sort_order": i + 1, "status": 1, "created_at": now, "updated_at": now,
            }
            for i, name in enumerate(DEPARTMENTS)
        ],
    )

    # 超级管理员账号（归入技术部）
    tech_dept_id = _id(bind, "sys_department", "name", "技术部")
    super_admin_role_id = _id(bind, "sys_role", "code", "super_admin")
    op.bulk_insert(
        sa.table(
            "sys_user",
            sa.column("username", sa.String), sa.column("password_hash", sa.String),
            sa.column("nickname", sa.String), sa.column("real_name", sa.String),
            sa.column("gender", mysql.TINYINT), sa.column("department_id", sa.BigInteger),
            sa.column("post", sa.String), sa.column("status", mysql.TINYINT),
            sa.column("need_reset_pwd", mysql.TINYINT), sa.column("failed_login_count", sa.Integer),
            sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "username": "admin",
                "password_hash": ADMIN_PASSWORD_HASH,
                "nickname": "超级管理员",
                "real_name": "系统管理员",
                "gender": 0,
                "department_id": tech_dept_id,
                "post": "系统管理员",
                "status": 1,
                "need_reset_pwd": 0,
                "failed_login_count": 0,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    admin_user_id = _id(bind, "sys_user", "username", "admin")
    op.bulk_insert(
        sa.table(
            "sys_user_role_relation",
            sa.column("user_id", sa.BigInteger), sa.column("role_id", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
        ),
        [{"user_id": admin_user_id, "role_id": super_admin_role_id, "created_at": now}],
    )

    # 菜单（先插全部，父级 ID 后置回填）
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
            for _, name, mtype, path, component, icon, pcode, sort in MENUS
        ],
    )
    for parent_name, name, *_ in MENUS:
        if parent_name is None:
            continue
        parent_id = _id(bind, "sys_menu", "name", parent_name)
        menu_id = _id(bind, "sys_menu", "name", name)
        bind.execute(
            sa.text("UPDATE sys_menu SET parent_id = :p WHERE id = :i"),
            {"p": parent_id, "i": menu_id},
        )

    # 权限标识字典
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
            for code, pname, module in PERMISSIONS
        ],
    )

    # 角色-菜单授权
    menu_id_map = {
        name: _id(bind, "sys_menu", "name", name)
        for _, name, *_ in MENUS
    }
    for role_code, granted in ROLE_MENU_NAMES.items():
        role_id = _id(bind, "sys_role", "code", role_code)
        menu_ids = list(menu_id_map.values()) if granted is None else [menu_id_map[n] for n in granted]
        op.bulk_insert(
            sa.table(
                "sys_role_menu_relation",
                sa.column("role_id", sa.BigInteger), sa.column("menu_id", sa.BigInteger),
                sa.column("created_at", sa.DateTime),
            ),
            [{"role_id": role_id, "menu_id": mid, "created_at": now} for mid in menu_ids],
        )

    # 菜单-权限关联（菜单绑定的权限标识 → sys_permission）
    for parent_name, name, mtype, path, component, icon, pcode, sort in MENUS:
        if not pcode:
            continue
        menu_id = menu_id_map[name]
        perm_id = _id(bind, "sys_permission", "code", pcode)
        op.bulk_insert(
            sa.table(
                "sys_menu_permission_relation",
                sa.column("menu_id", sa.BigInteger), sa.column("permission_id", sa.BigInteger),
                sa.column("created_at", sa.DateTime),
            ),
            [{"menu_id": menu_id, "permission_id": perm_id, "created_at": now}],
        )

    # 字典类型与字典项
    op.bulk_insert(
        sa.table(
            "sys_dict_type",
            sa.column("dict_name", sa.String), sa.column("dict_code", sa.String),
            sa.column("description", sa.String), sa.column("status", mysql.TINYINT),
            sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        ),
        [
            {"dict_name": dname, "dict_code": code, "description": dname,
             "status": 1, "created_at": now, "updated_at": now}
            for code, (dname, _items) in DICTS.items()
        ],
    )
    dict_items = [
        {"dict_code": code, "item_label": label, "item_value": value, "sort_order": i,
         "status": 1, "created_at": now, "updated_at": now}
        for code, (_dname, items) in DICTS.items()
        for i, (label, value) in enumerate(items)
    ]
    op.bulk_insert(
        sa.table(
            "sys_dict_item",
            sa.column("dict_code", sa.String), sa.column("item_label", sa.String),
            sa.column("item_value", sa.String), sa.column("sort_order", sa.Integer),
            sa.column("status", mysql.TINYINT), sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        dict_items,
    )

    # 系统配置
    op.bulk_insert(
        sa.table(
            "sys_config",
            sa.column("config_key", sa.String), sa.column("config_name", sa.String),
            sa.column("config_value", sa.String), sa.column("description", sa.String),
            sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        ),
        [
            {"config_key": "system.name", "config_name": "系统名称", "config_value": "企业管理系统",
             "description": "登录页与系统标题展示", "created_at": now, "updated_at": now}
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 先拆除环中外键，再按依赖逆序删表
    op.drop_constraint("fk_department_leader", "sys_department", type_="foreignkey")
    op.drop_table("sys_menu_permission_relation")
    op.drop_table("sys_role_menu_relation")
    op.drop_table("sys_user_role_relation")
    op.drop_table("sys_invitation_log")
    op.drop_table("sys_invitation")
    op.drop_table("sys_registration_approval")
    op.drop_table("sys_password_recovery_code")
    op.drop_table("sys_log")
    op.drop_table("sys_dict_item")
    op.drop_table("sys_dict_type")
    op.drop_table("sys_config")
    op.drop_table("sys_menu")
    op.drop_table("sys_permission")
    op.drop_table("sys_user")
    op.drop_table("sys_role")
    op.drop_table("sys_department")
