"""认证接口的请求体模型。"""
from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class RecoverySendIn(BaseModel):
    """找回密码第一步：账号名（验证码生成）。"""
    username: str


class RecoveryResetIn(BaseModel):
    """找回密码第二步：账号 + 验证码 + 新密码。"""
    username: str
    code: str
    new_password: str
