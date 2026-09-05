"""考勤模块模型：att_record 考勤记录表、att_rule 考勤薪资规则表。"""
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, Time, UniqueConstraint
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttRecord(Base):
    __tablename__ = "att_record"
    __table_args__ = (
        UniqueConstraint("user_id", "att_date", name="uk_att_user_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="员工")
    dept_id: Mapped[int | None] = mapped_column(BigInteger, comment="部门快照（记录时员工所属部门）")
    att_date: Mapped[date] = mapped_column(Date, nullable=False, comment="考勤日期")
    check_in: Mapped[time | None] = mapped_column(Time, comment="签到时间")
    check_out: Mapped[time | None] = mapped_column(Time, comment="签退时间")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="考勤状态：normal/late/early_leave/miss_check/absent/leave/business_trip",
    )
    location: Mapped[str | None] = mapped_column(String(128), comment="考勤地点")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")
    source: Mapped[int] = mapped_column(TINYINT, default=1, comment="1导入 2手动")
    importer_id: Mapped[int | None] = mapped_column(BigInteger, comment="导入/补录人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class AttRule(Base):
    __tablename__ = "att_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status_key: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, comment="对应 att_record.status")
    adjust_type: Mapped[int] = mapped_column(TINYINT, nullable=False, comment="1奖励 2扣款")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="每次/每日金额")
    enabled: Mapped[int] = mapped_column(TINYINT, default=1, comment="是否启用：0否 1是")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
