"""系统参数配置出入参（预置项仅允许更新，不提供新增/删除）。"""
from pydantic import BaseModel, Field


class ConfigUpdateIn(BaseModel):
    config_value: str | None = Field(default=None, description="配置值")
    description: str | None = Field(default=None, max_length=255)
