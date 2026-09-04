"""sys_menu_permission_relation 菜单权限关联表模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysMenuPermissionRelation(Base):
    __tablename__ = "sys_menu_permission_relation"
    __table_args__ = (UniqueConstraint("menu_id", "permission_id", name="uk_menu_permission"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    menu_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_menu.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_permission.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
