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


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
