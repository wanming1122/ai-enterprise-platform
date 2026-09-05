"""NL2SQL 出入参（M4-T2）。"""
from typing import Literal

from pydantic import BaseModel, Field


class NL2SQLGenerateIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000, description="自然语言问题")


class NL2SQLReviewIn(BaseModel):
    action: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=255, description="审核意见（可选）")
