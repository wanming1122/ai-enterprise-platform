"""产品数据出入参（M4-T2）。"""
from pydantic import BaseModel, Field, field_validator

PRODUCT_STATUS = (1, 0)  # 1上架 0下架（2软删仅内部使用）


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=32)
    price: float | None = Field(default=None, ge=0)
    stock: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=255)
    status: int = 1

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: int) -> int:
        if v not in PRODUCT_STATUS:
            raise ValueError("状态仅支持 1上架 / 0下架")
        return v


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=32)
    price: float | None = Field(default=None, ge=0)
    stock: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=255)
    status: int | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: int | None) -> int | None:
        if v is not None and v not in PRODUCT_STATUS:
            raise ValueError("状态仅支持 1上架 / 0下架")
        return v
