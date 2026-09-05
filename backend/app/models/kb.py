"""RAG 知识库模块模型：kb_knowledge_base、kb_file、kb_chunk（设计方案 11.8）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KBKnowledgeBase(Base):
    __tablename__ = "kb_knowledge_base"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="知识库名称")
    description: Mapped[str | None] = mapped_column(String(255), comment="知识库描述")
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False, comment="入库使用的Embedding模型标识")
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False, comment="向量维度，创建后不可变更")
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, comment="切片长度（字符）")
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=80, comment="相邻切片重叠字符数")
    collection_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="Chroma collection名 kb_{id}")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1启用 0停用 2软删除")
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="创建人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class KBFile(Base):
    __tablename__ = "kb_file"
    __table_args__ = (
        UniqueConstraint("kb_id", "content_hash", name="uk_kbfile_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_knowledge_base.id"), nullable=False, comment="所属知识库")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    file_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="pdf/docx/md/txt")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="字节数")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA-256，同库去重")
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False, comment="media目录相对路径")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, comment="切片总数")
    parse_status: Mapped[int] = mapped_column(TINYINT, default=0, comment="0待解析 1解析中 2已入库 3失败")
    fail_reason: Mapped[str | None] = mapped_column(String(255), comment="解析失败原因")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1正常 2软删除")
    uploader_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="上传人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class KBChunk(Base):
    __tablename__ = "kb_chunk"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_file.id"), nullable=False, comment="所属文件")
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="冗余字段，支撑按库重建索引")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="文件内切片序号")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="切片文本")
    char_count: Mapped[int | None] = mapped_column(Integer, comment="切片字符数")
    title_path: Mapped[str | None] = mapped_column(String(255), comment="标题路径，如 员工手册>考勤制度>迟到处理")
    page: Mapped[int | None] = mapped_column(Integer, comment="页码，PDF类文档生效")
    chunk_type: Mapped[str] = mapped_column(String(16), default="text", comment="text/table/image_description")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1有效 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
