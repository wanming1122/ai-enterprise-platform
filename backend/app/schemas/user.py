"""用户管理的请求体模型。"""
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import PhoneStr


class UserCreate(BaseModel):
    username: str
    password: str
    nickname: str | None = None
    real_name: str | None = None
    gender: int = 0
    birthday: date | None = None
    email: str | None = None
    phone: PhoneStr
    department_id: int = Field(description="所属部门")
    position_id: int = Field(description="职位")
    post: str | None = None
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    nickname: str | None = None
    real_name: str | None = None
    gender: int | None = None
    birthday: date | None = None
    email: str | None = None
    phone: PhoneStr
    department_id: int = Field(description="所属部门")
    position_id: int = Field(description="职位")
    post: str | None = None
    role_ids: list[int] | None = None
