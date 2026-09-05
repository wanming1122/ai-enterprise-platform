"""考勤管理的请求体模型。"""
from pydantic import BaseModel


class AttRecordCreate(BaseModel):
    """手动补录：员工 + 日期 + 签到签退 + 状态 + 地点备注。"""
    user_id: int
    att_date: str  # YYYY-MM-DD
    check_in: str | None = None  # HH:MM 或 HH:MM:SS
    check_out: str | None = None
    status: str
    location: str | None = None
    remark: str | None = None


class AttRuleUpdate(BaseModel):
    adjust_type: int | None = None
    amount: float | None = None
    enabled: int | None = None
