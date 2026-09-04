"""sys_registration_approval 注册审批表模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysRegistrationApproval(Base):
    __tablename__ = "sys_registration_approval"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False, comment="申请账号快照")
    real_name: Mapped[str | None] = mapped_column(String(64), comment="姓名")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    email: Mapped[str | None] = mapped_column(String(128), comment="邮箱")
    apply_role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_role.id"), nullable=False, comment="申请角色"
    )
    status: Mapped[int] = mapped_column(TINYINT, default=0, comment="0待审批 1通过 2驳回")
    apply_comment: Mapped[str | None] = mapped_column(String(255), comment="申请说明")
    review_comment: Mapped[str | None] = mapped_column(String(255), comment="审批意见")
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), comment="审批人")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="审批时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
