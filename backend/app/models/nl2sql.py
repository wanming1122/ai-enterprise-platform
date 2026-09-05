"""NL2SQL 模块模型（M4-T2）：product 产品数据、nl2sql_record 生成记录（开发文档 5.4）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    """产品数据表：NL2SQL 查询标的，status=2 软删行不参与查询。"""

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="产品名称")
    category: Mapped[str | None] = mapped_column(String(32), comment="产品分类")
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="价格")
    stock: Mapped[int | None] = mapped_column(Integer, default=0, comment="库存")
    description: Mapped[str | None] = mapped_column(String(255), comment="产品描述")
    status: Mapped[int] = mapped_column(TINYINT, default=1, nullable=False, comment="1上架 0下架 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class NL2SQLRecord(Base):
    """自然语言生成 SQL 记录：生成→审核→执行全流程留痕。"""

    __tablename__ = "nl2sql_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="提问人")
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="自然语言原句")
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False, comment="生成的SQL")
    review_status: Mapped[int] = mapped_column(
        TINYINT, default=0, nullable=False, comment="0待审核 1通过 2驳回 3已执行"
    )
    review_comment: Mapped[str | None] = mapped_column(String(255), comment="审核意见")
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, comment="审核人")
    result_json: Mapped[str | None] = mapped_column(Text, comment="执行结果JSON（columns+rows）")
    execution_ms: Mapped[int | None] = mapped_column(Integer, comment="执行耗时（毫秒）")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="执行时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
