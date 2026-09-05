"""知识库服务（M3-T1）：库 CRUD、文件上传校验与软删、切片预览。

解析入库/向量化/Chroma 同步在 M3-T2 的 kb_rag_service 中实现，本模块只负责管理面。
"""
import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.kb import KBChunk, KBFile, KBKnowledgeBase
from app.models.user import SysUser
from app.schemas.kb import KBCreate, KBUpdate
from app.services.operation_log_service import write_log

ALLOWED_TYPES = {"pdf": "pdf", "docx": "docx", "md": "md", "txt": "txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
PARSE_STATUS = {0: "待解析", 1: "解析中", 2: "已入库", 3: "失败"}


def _check_magic(head: bytes, file_type: str) -> bool:
    """文件头魔数校验，防止伪造后缀。"""
    if file_type == "pdf":
        return head.startswith(b"%PDF-")
    if file_type == "docx":
        return head.startswith(b"PK\x03\x04")  # zip 容器
    return True  # md/txt 为纯文本，无固定魔数


def serialize_kb(db: Session, kb: KBKnowledgeBase) -> dict:
    file_count = db.scalar(
        select(func.count()).select_from(KBFile).where(KBFile.kb_id == kb.id, KBFile.status != 2)
    ) or 0
    chunk_count = db.scalar(
        select(func.count()).select_from(KBChunk).where(KBChunk.kb_id == kb.id, KBChunk.status != 2)
    ) or 0
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "embedding_model": kb.embedding_model,
        "embedding_dimension": kb.embedding_dimension,
        "chunk_size": kb.chunk_size,
        "chunk_overlap": kb.chunk_overlap,
        "collection_name": kb.collection_name,
        "status": kb.status,
        "file_count": file_count,
        "chunk_count": chunk_count,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
    }


def serialize_file(f: KBFile) -> dict:
    return {
        "id": f.id,
        "kb_id": f.kb_id,
        "file_name": f.file_name,
        "file_type": f.file_type,
        "file_size": f.file_size,
        "chunk_count": f.chunk_count,
        "parse_status": f.parse_status,
        "parse_status_label": PARSE_STATUS.get(f.parse_status, ""),
        "fail_reason": f.fail_reason,
        "status": f.status,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def serialize_chunk(c: KBChunk) -> dict:
    return {
        "id": c.id,
        "chunk_index": c.chunk_index,
        "content": c.content,
        "char_count": c.char_count,
        "title_path": c.title_path,
        "page": c.page,
        "chunk_type": c.chunk_type,
    }


def list_kbs(db: Session, *, keyword: str | None = None, page: int = 1, page_size: int = 20):
    q = select(KBKnowledgeBase).where(KBKnowledgeBase.status != 2)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(KBKnowledgeBase.name.like(like))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    kbs = db.scalars(q.order_by(KBKnowledgeBase.id).offset((page - 1) * page_size).limit(page_size)).all()
    return [serialize_kb(db, k) for k in kbs], total


def get_kb(db: Session, kb_id: int) -> KBKnowledgeBase:
    kb = db.get(KBKnowledgeBase, kb_id)
    if kb is None or kb.status == 2:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


def create_kb(db: Session, data: KBCreate, operator: SysUser) -> dict:
    if db.scalar(select(KBKnowledgeBase.id).where(KBKnowledgeBase.name == data.name, KBKnowledgeBase.status != 2)):
        raise HTTPException(status_code=422, detail="知识库名称已存在")
    if data.chunk_size < 100 or data.chunk_overlap < 0 or data.chunk_overlap >= data.chunk_size:
        raise HTTPException(status_code=422, detail="切分参数不合法：chunk_size≥100 且 0≤overlap<size")

    # 创建时锁定向量模型与维度：取启用的默认向量配置（无则 .env 兜底），名称以实际调用为准
    from app.services.ai_model_service import resolve_embedding_config
    from app.services.kb_rag_service import probe_embedding_dimension

    embedding_config = resolve_embedding_config(db)
    embedding_model = embedding_config["model_name"]
    dimension = data.embedding_dimension
    if dimension is None:
        try:
            dimension = probe_embedding_dimension(embedding_config)
        except HTTPException:
            raise
        if dimension is None:
            raise HTTPException(
                status_code=422,
                detail="无法探测向量维度：请显式指定 embedding_dimension，或配置 Embedding API 密钥",
            )

    kb = KBKnowledgeBase(
        name=data.name, description=data.description,
        embedding_model=embedding_model, embedding_dimension=dimension,
        chunk_size=data.chunk_size, chunk_overlap=data.chunk_overlap,
        collection_name="pending", creator_id=operator.id, status=1,
    )
    db.add(kb)
    db.flush()
    kb.collection_name = f"kb_{kb.id}"  # 规则 kb_{id}
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="知识库",
              action="新建知识库", params=data.model_dump(), result=1)
    return serialize_kb(db, kb)


def update_kb(db: Session, kb_id: int, data: KBUpdate, operator: SysUser) -> dict:
    kb = get_kb(db, kb_id)
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"]:
        exists = db.scalar(
            select(KBKnowledgeBase.id).where(
                KBKnowledgeBase.name == updates["name"], KBKnowledgeBase.id != kb_id,
                KBKnowledgeBase.status != 2,
            )
        )
        if exists:
            raise HTTPException(status_code=422, detail="知识库名称已存在")
    if "chunk_size" in updates and updates["chunk_size"] is not None and updates["chunk_size"] < 100:
        raise HTTPException(status_code=422, detail="chunk_size 需不小于100")
    if "chunk_overlap" in updates and updates["chunk_overlap"] is not None:
        if updates["chunk_overlap"] < 0 or updates["chunk_overlap"] >= (
            updates.get("chunk_size") or kb.chunk_size
        ):
            raise HTTPException(status_code=422, detail="overlap 需满足 0≤overlap<size")
    for field, value in updates.items():
        setattr(kb, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="知识库",
              action="编辑知识库", params={"id": kb_id, **updates}, result=1)
    return serialize_kb(db, kb)


def delete_kb(db: Session, kb_id: int, operator: SysUser) -> None:
    """软删除知识库及其下全部文件（Chroma 侧同步在 T2 接入）。"""
    kb = get_kb(db, kb_id)
    kb.status = 2
    for f in db.scalars(select(KBFile).where(KBFile.kb_id == kb_id, KBFile.status != 2)).all():
        f.status = 2
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="知识库",
              action="删除知识库", params={"id": kb_id}, result=1)


def upload_file(db: Session, kb: KBKnowledgeBase, file: UploadFile, operator: SysUser) -> dict:
    """上传文件：后缀白名单 + 魔数校验 + 大小上限 + 同库哈希去重，落盘待解析。"""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="仅支持 pdf/docx/md/txt 文件")

    content = file.file.read()
    if len(content) == 0:
        raise HTTPException(status_code=422, detail="文件为空")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="文件超过 50MB 上限")
    if not _check_magic(content[:16], ext):
        raise HTTPException(status_code=422, detail="文件内容与后缀不符")

    content_hash = hashlib.sha256(content).hexdigest()
    dup = db.scalar(
        select(KBFile.id).where(KBFile.kb_id == kb.id, KBFile.content_hash == content_hash, KBFile.status != 2)
    )
    if dup is not None:
        raise HTTPException(status_code=422, detail="同知识库已存在相同内容的文件")

    rel_dir = Path("kb") / str(kb.id)
    abs_dir = Path(settings.MEDIA_DIR) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    rel_path = rel_dir / f"{uuid.uuid4().hex}.{ext}"
    (Path(settings.MEDIA_DIR) / rel_path).write_bytes(content)

    kb_file = KBFile(
        kb_id=kb.id, file_name=filename, file_type=ext, file_size=len(content),
        content_hash=content_hash, storage_path=str(rel_path),
        chunk_count=0, parse_status=0, status=1, uploader_id=operator.id,
    )
    db.add(kb_file)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="知识库",
              action="上传文件", params={"kb_id": kb.id, "file_name": filename, "size": len(content)}, result=1)
    return serialize_file(kb_file)


def list_files(db: Session, kb_id: int, *, parse_status: int | None = None,
               page: int = 1, page_size: int = 20):
    get_kb(db, kb_id)
    q = select(KBFile).where(KBFile.kb_id == kb_id, KBFile.status != 2)
    if parse_status is not None:
        q = q.where(KBFile.parse_status == parse_status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    files = db.scalars(
        q.order_by(KBFile.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_file(f) for f in files], total


def get_file(db: Session, file_id: int) -> KBFile:
    f = db.get(KBFile, file_id)
    if f is None or f.status == 2:
        raise HTTPException(status_code=404, detail="文件不存在")
    return f


def delete_file(db: Session, file_id: int, operator: SysUser) -> None:
    """软删除文件（Chroma 侧同步标记在 T2 接入后生效）。"""
    f = get_file(db, file_id)
    f.status = 2
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="知识库",
              action="删除文件", params={"file_id": file_id}, result=1)


def list_chunks(db: Session, file_id: int, *, page: int = 1, page_size: int = 20):
    f = get_file(db, file_id)
    q = select(KBChunk).where(KBChunk.file_id == f.id, KBChunk.status != 2)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    chunks = db.scalars(
        q.order_by(KBChunk.chunk_index).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_chunk(c) for c in chunks], total
