"""个人中心的请求体模型。"""
from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    """本人资料修改：不含账号、部门、职位、角色等管理字段。"""
    nickname: str | None = None
    real_name: str | None = None
    gender: int | None = None
    birthday: str | None = None  # YYYY-MM-DD
    email: str | None = None
    phone: str | None = None
    social_account: str | None = None
    avatar: str | None = None  # Data URL


class PreferencesUpdate(BaseModel):
    """个人偏好设置（合并进 sys_user.preferences JSON，仅白名单键）。"""
    default_home: str | None = None      # 登录后默认落地页路径，如 /dashboard
    sidebar_collapsed: bool | None = None  # 侧边菜单默认折叠
    notify_enabled: bool | None = None     # 站内消息提醒开关
    theme: str | None = None               # 界面主题：light 浅色 / dark 深色


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
