"""职位管理的请求体模型。"""
from decimal import Decimal

from pydantic import BaseModel


class PositionCreate(BaseModel):
    name: str
    code: str
    level: int = 1
    base_salary: Decimal
    role_id: int | None = None
    description: str | None = None
    status: int = 1


class PositionUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    level: int | None = None
    base_salary: Decimal | None = None
    role_id: int | None = None
    description: str | None = None
    status: int | None = None
