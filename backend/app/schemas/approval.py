"""注册审批出入参。"""
from pydantic import BaseModel, Field


class RegisterApplyIn(BaseModel):
    """公开的注册申请入参（未登录可提交，创建停用账号等待审批）。"""
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)
    real_name: str = Field(min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=128)
    apply_role_id: int = Field(description="申请角色")
    apply_comment: str | None = Field(default=None, max_length=255, description="申请说明")


class ApprovalRejectIn(BaseModel):
    comment: str | None = Field(default=None, max_length=255, description="驳回意见")
