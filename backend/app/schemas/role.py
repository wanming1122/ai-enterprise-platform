"""角色管理的请求体模型。"""
from pydantic import BaseModel


class RoleCreate(BaseModel):
    name: str
    code: str
    role_type: int = 3
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    role_type: int | None = None
    description: str | None = None
    status: int | None = None


class RoleAuth(BaseModel):
    menu_ids: list[int]
