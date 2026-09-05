"""权限标识字典的请求体模型。"""
from pydantic import BaseModel


class PermissionCreate(BaseModel):
    name: str
    code: str
    module: str | None = None
    description: str | None = None


class PermissionUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    module: str | None = None
    description: str | None = None
