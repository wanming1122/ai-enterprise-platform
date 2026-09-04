"""用户管理的请求体模型。"""
from datetime import date

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    nickname: str | None = None
    real_name: str | None = None
    gender: int = 0
    birthday: date | None = None
    email: str | None = None
    phone: str | None = None
    department_id: int | None = None
    post: str | None = None
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    nickname: str | None = None
    real_name: str | None = None
    gender: int | None = None
    birthday: date | None = None
    email: str | None = None
    phone: str | None = None
    department_id: int | None = None
    post: str | None = None
    role_ids: list[int] | None = None
