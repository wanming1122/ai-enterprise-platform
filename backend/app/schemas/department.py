"""部门管理的请求体模型。"""
from pydantic import BaseModel


class DeptCreate(BaseModel):
    name: str
    parent_id: int | None = None
    leader_id: int | None = None
    phone: str | None = None
    email: str | None = None
    description: str | None = None
    sort_order: int = 0
    status: int = 1


class DeptUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    leader_id: int | None = None
    phone: str | None = None
    email: str | None = None
    description: str | None = None
    sort_order: int | None = None
    status: int | None = None


class DeptSortItem(BaseModel):
    id: int
    sort_order: int
