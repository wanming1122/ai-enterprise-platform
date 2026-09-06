"""字典管理出入参。"""
from pydantic import BaseModel, Field


class DictTypeCreate(BaseModel):
    dict_name: str = Field(min_length=1, max_length=64)
    dict_code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    description: str | None = Field(default=None, max_length=255)


class DictTypeUpdate(BaseModel):
    dict_name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    status: int | None = None


class DictItemCreate(BaseModel):
    item_label: str = Field(min_length=1, max_length=64)
    item_value: str = Field(min_length=1, max_length=64)
    sort_order: int = 0


class DictItemUpdate(BaseModel):
    item_label: str | None = Field(default=None, min_length=1, max_length=64)
    item_value: str | None = Field(default=None, min_length=1, max_length=64)
    sort_order: int | None = None
    status: int | None = None
