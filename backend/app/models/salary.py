"""薪资模块模型：sal_payroll 月度工资单表、sal_adjustment 手动奖惩表。"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SalPayroll(Base):
    __tablename__ = "sal_payroll"
    __table_args__ = (
        UniqueConstraint("user_id", "year_month", name="uk_sal_user_month"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="员工")
    year_month: Mapped[str] = mapped_column(String(7), nullable=False, comment="所属月份，格式YYYY-MM")
    position_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="职位快照")
    base_salary: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="职位基本工资快照")
    attendance_adjust: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, comment="考勤增减合计")
    manual_adjust: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, comment="手动奖惩合计")
    total_salary: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="应发合计")
    status: Mapped[int] = mapped_column(TINYINT, default=0, comment="0草稿 1已确认 2已发放")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, comment="生成/确认操作人")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="确认时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class SalAdjustment(Base):
    __tablename__ = "sal_adjustment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="员工")
    adjust_type: Mapped[int] = mapped_column(TINYINT, nullable=False, comment="1奖励 2罚款")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="金额")
    reason: Mapped[str] = mapped_column(String(255), nullable=False, comment="事由")
    year_month: Mapped[str | None] = mapped_column(String(7), comment="归属月份，生成工资单时汇总")
    operator_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="录入人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
