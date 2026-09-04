"""sys_dict_type 字典类型表 与 sys_dict_item 字典项表模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysDictType(Base):
    __tablename__ = "sys_dict_type"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dict_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="字典名称")
    dict_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="字典编码")
    description: Mapped[str | None] = mapped_column(String(255), comment="字典说明")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1启用 0停用 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class SysDictItem(Base):
    __tablename__ = "sys_dict_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dict_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="所属字典编码")
    item_label: Mapped[str] = mapped_column(String(64), nullable=False, comment="字典项标签")
    item_value: Mapped[str] = mapped_column(String(64), nullable=False, comment="字典项值")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1启用 0停用 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
