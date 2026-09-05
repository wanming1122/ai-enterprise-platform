"""知识库管理的请求体模型。"""
from pydantic import BaseModel


class KBCreate(BaseModel):
    name: str
    description: str | None = None
    chunk_size: int = 500
    chunk_overlap: int = 80
    # 可选：由调用方显式指定向量维度（跳过探测）；未传时创建流程尝试用 embedding API 探测
    embedding_dimension: int | None = None


class KBUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
