"""菜单管理的请求体模型。"""
from pydantic import BaseModel


class MenuCreate(BaseModel):
    parent_id: int | None = None
    name: str
    type: int = 2
    path: str | None = None
    component: str | None = None
    icon: str | None = None
    permission_code: str | None = None
    visible: int = 1
    is_external: int = 0
    sort_order: int = 0
    status: int = 1


class MenuUpdate(BaseModel):
    parent_id: int | None = None
    name: str | None = None
    type: int | None = None
    path: str | None = None
    component: str | None = None
    icon: str | None = None
    permission_code: str | None = None
    visible: int | None = None
    is_external: int | None = None
    sort_order: int | None = None
    status: int | None = None


class MenuSortItem(BaseModel):
    id: int
    sort_order: int
