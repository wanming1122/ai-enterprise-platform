"""模型注册入口：侧载全部模型，确保 Base.metadata 完整，供 Alembic 扫描。"""
from app.models.user import SysUser
from app.models.department import SysDepartment
from app.models.position import SysPosition
from app.models.role import SysRole
from app.models.user_role_relation import SysUserRoleRelation
from app.models.menu import SysMenu
from app.models.role_menu_relation import SysRoleMenuRelation
from app.models.permission import SysPermission
from app.models.menu_permission_relation import SysMenuPermissionRelation
from app.models.registration_approval import SysRegistrationApproval
from app.models.invitation import SysInvitation, SysInvitationLog
from app.models.password_recovery_code import SysPasswordRecoveryCode
from app.models.log import SysLog
from app.models.config import SysConfig
from app.models.dict import SysDictType, SysDictItem

__all__ = [
    "SysUser",
    "SysDepartment",
    "SysPosition",
    "SysRole",
    "SysUserRoleRelation",
    "SysMenu",
    "SysRoleMenuRelation",
    "SysPermission",
    "SysMenuPermissionRelation",
    "SysRegistrationApproval",
    "SysInvitation",
    "SysInvitationLog",
    "SysPasswordRecoveryCode",
    "SysLog",
    "SysConfig",
    "SysDictType",
    "SysDictItem",
]
