"""薪资管理的请求体模型。"""
from pydantic import BaseModel


class SalaryGenerate(BaseModel):
    year_month: str  # YYYY-MM
    user_ids: list[int] | None = None  # 缺省生成全部有职位的启用员工


class SalAdjustmentCreate(BaseModel):
    user_id: int
    adjust_type: int  # 1奖励 2罚款
    amount: float
    reason: str
    year_month: str | None = None


class SalAdjustmentQuery(BaseModel):
    year_month: str | None = None
    user_id: int | None = None
