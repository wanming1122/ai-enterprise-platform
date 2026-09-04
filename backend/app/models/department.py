"""sys_department 部门表模型（多级树形）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysDepartment(Base):
    __tablename__ = "sys_department"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="部门名称")
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_department.id"), comment="上级部门ID"
    )
    leader_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), comment="部门负责人"
    )
    phone: Mapped[str | None] = mapped_column(String(20), comment="联系电话")
    email: Mapped[str | None] = mapped_column(String(128), comment="邮箱")
    description: Mapped[str | None] = mapped_column(String(255), comment="部门描述")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1启用 0停用 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
