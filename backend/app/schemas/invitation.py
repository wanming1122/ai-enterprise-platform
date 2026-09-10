"""入职邀请出入参。"""
from pydantic import BaseModel, Field

from app.schemas.common import PhoneStr


class InvitationCreateIn(BaseModel):
    name: str | None = Field(default=None, max_length=64, description="被邀请人姓名（选填）")
    phone: PhoneStr
    email: str | None = Field(default=None, max_length=128)
    department_id: int = Field(description="预设部门（必填）")
    role_id: int = Field(description="预设角色（必填）")
    post: str | None = Field(default=None, max_length=64, description="预设岗位")
    expires_days: int = Field(default=3, ge=1, le=30, description="有效期（天）")
    remark: str | None = Field(default=None, max_length=255)


class InvitationAcceptIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)
