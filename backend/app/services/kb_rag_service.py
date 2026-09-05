"""RAG 入库与检索核心（M3-T2/T3）：文档解析、清洗切分、Embedding 向量化、Chroma 双写。

- Embedding：智谱 embedding-3（OpenAI 兼容端点，密钥走 .env），维度创建库时锁定
- 向量库：Chroma PersistentClient，一库一 collection（kb_{id}），cosine 空间
- 双写：切片文本与元数据写 MySQL kb_chunk，向量与 metadata 写 Chroma
"""
import re
import uuid
from datetime import datetime
from pathlib import Path

import chromadb
import httpx
import pdfplumber
from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.kb import KBChunk, KBFile, KBKnowledgeBase
from app.models.user import SysUser
from app.services.operation_log_service import write_log

ZHIPU_EMBEDDING_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
EMBED_BATCH_SIZE = 16
SEPARATORS = ["\n\n", "\n", "。", "；", "，", " "]
CHROMA_CLIENT = chromadb.PersistentClient(path=settings.CHROMA_DIR)


# ---------- Embedding ----------

def _zhipu_embed(texts: list[str], dimensions: int) -> list[list[float]]:
    """调用智谱 embedding-3，OpenAI 兼容格式，批量分片请求。"""
    key = settings.ZHIPU_API_KEY
    if not key:
        raise HTTPException(status_code=422, detail="未配置 Embedding API 密钥（ZHIPU_API_KEY）")
    vectors: list[list[float]] = []
    with httpx.Client(timeout=60) as client:
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i:i + EMBED_BATCH_SIZE]
            for attempt in range(2):  # 失败重试一次
                r = client.post(
                    ZHIPU_EMBEDDING_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": "embedding-3", "input": batch, "dimensions": dimensions},
                )
                if r.status_code == 200:
                    data = sorted(r.json()["data"], key=lambda x: x["index"])
                    vectors.extend(item["embedding"] for item in data)
                    break
                if attempt == 1:
                    raise HTTPException(status_code=422, detail=f"向量化失败：{r.text[:200]}")
    return vectors


def probe_embedding_dimension(model: str = "embedding-3") -> int:
    """创建知识库时探测向量维度（探针一次，写入 kb 表后锁定）。"""
    return len(_zhipu_embed(["维度探针"], 1024)[0])


def embed_texts(texts: list[str], dimensions: int) -> list[list[float]]:
    return _zhipu_embed(texts, dimensions)


# ---------- 解析与切分 ----------

def _clean(text: str) -> str:
    """清洗：规整空白与多余空行。"""
    text = text.replace("\x00", "")
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: list[str] = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip()


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    """递归字符切分：按分隔符优先级归组，块间携带 overlap 字符。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    segments: list[str] = []
    for sep in SEPARATORS:
        if sep and sep in text:
            segments = [p for p in text.split(sep) if p.strip()]
            if len(segments) > 1:
                # 二次细分超长段
                flat: list[str] = []
                for seg in segments:
                    flat.extend(_split_text(seg, size, 0) if len(seg) > size else [seg])
                break
    if not segments:
        segments = [text[i:i + size] for i in range(0, len(text), size - overlap)]  # 硬切兜底

    chunks: list[str] = []
    current = ""
    for seg in segments:
        candidate = f"{current}{sep if current else ''}{seg}" if current else seg
        # 兼容 sep 已并入 segments 拆分的场景：手动补分隔符
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            tail = current[-overlap:] if current and overlap > 0 else ""
            current = (tail + seg)[:size] if tail else seg[:size]
            while len(seg) > size:  # 单段超长硬切
                chunks.append(seg[:size])
                seg = seg[size - overlap:]
                current = seg
    if current:
        chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


def _table_to_markdown(rows: list[list[str | None]]) -> str:
    """表格转 Markdown，空单元格以空串占位。"""
    rows = [[("" if c is None else str(c).strip().replace("\n", " ")) for c in row] for row in rows]
    if not rows:
        return ""
    header = rows[0]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for row in rows[1:]:
        row = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(row[: len(header)]) + " |")
    return "\n".join(lines)


def _split_table(rows: list[list[str | None]], size: int) -> list[str]:
    """大表按行分组切分，每组重复表头。"""
    md = _table_to_markdown(rows)
    if len(md) <= size or len(rows) <= 2:
        return [md] if md.strip() else []
    header, body = rows[0], rows[1:]
    group_size = max(5, len(body) * size // max(1, len(md)) or 5)
    chunks = []
    for i in range(0, len(body), group_size):
        part = _table_to_markdown([header, *body[i:i + group_size]])
        if part.strip():
            chunks.append(part)
    return chunks


def _parse_pdf(path: Path) -> list[dict]:
    """PDF：逐页文本 + 表格，携带页码。"""
    items: list[dict] = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                for part in _split_table(table, 500):
                    items.append({"content": part, "title_path": None, "page": page_no, "chunk_type": "table"})
            text = page.extract_text() or ""
            if text.strip():
                items.append({"content": _clean(text), "title_path": None, "page": page_no, "chunk_type": "text"})
    return items


def _parse_docx(path: Path) -> list[dict]:
    """Word：按标题样式维护标题路径，段落成文、表格转 Markdown。"""
    items: list[dict] = []
    doc = DocxDocument(str(path))
    title_stack: list[str] = []

    def add_text(text: str) -> None:
        if text.strip():
            items.append({"content": _clean(text), "title_path": ">".join(title_stack) or None,
                          "page": None, "chunk_type": "text"})

    buffer: list[str] = []
    for element in doc.element.body:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = DocxParagraph(element, doc)
            style = (para.style.name or "") if para.style is not None else ""
            if style.startswith("Heading") or style.startswith("标题"):
                if buffer:
                    add_text("\n".join(buffer))
                    buffer = []
                level = "".join(ch for ch in style if ch.isdigit()) or "1"
                level = int(level)
                title_stack[:] = title_stack[: level - 1]
                title_stack.append(para.text.strip())
            elif para.text.strip():
                buffer.append(para.text)
        elif tag == "tbl":
            if buffer:
                add_text("\n".join(buffer))
                buffer = []
            table = DocxTable(element, doc)
            rows = [[c.text for c in row.cells] for row in table.rows]
            for part in _split_table(rows, 500):
                items.append({"content": part, "title_path": ">".join(title_stack) or None,
                              "page": None, "chunk_type": "table"})
    if buffer:
        add_text("\n".join(buffer))
    return items


def _parse_markdown(text: str) -> list[dict]:
    """Markdown：按标题层级切分并记录标题路径。"""
    items: list[dict] = []
    title_stack: list[str] = []
    section: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if section:
                items.append({"content": _clean("\n".join(section)),
                              "title_path": ">".join(title_stack) or None,
                              "page": None, "chunk_type": "text"})
                section = []
            level = len(m.group(1))
            title_stack[:] = title_stack[: level - 1]
            title_stack.append(m.group(2).strip())
        else:
            section.append(line)
    if section:
        items.append({"content": _clean("\n".join(section)),
                      "title_path": ">".join(title_stack) or None,
                      "page": None, "chunk_type": "text"})
    return items


def parse_file_to_items(file_type: str, path: Path) -> list[dict]:
    """按类型解析文件为内容片段列表（未切分）。"""
    if file_type == "pdf":
        return _parse_pdf(path)
    if file_type == "docx":
        return _parse_docx(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="ignore")
    if file_type == "md":
        return _parse_markdown(text)
    return [{"content": _clean(text), "title_path": None, "page": None, "chunk_type": "text"}]


def build_chunks(kb: KBKnowledgeBase, file_id: int, items: list[dict]) -> list[dict]:
    """将解析片段切分为最终切片（表格整块直通，文本走递归切分）。"""
    chunks: list[dict] = []
    index = 0
    for item in items:
        if item["chunk_type"] == "table":
            parts = [item["content"]] if item["content"] else []
        else:
            parts = _split_text(item["content"], kb.chunk_size, kb.chunk_overlap)
        for part in parts:
            chunks.append({
                "file_id": file_id, "kb_id": kb.id, "chunk_index": index,
                "content": part, "char_count": len(part),
                "title_path": item["title_path"], "page": item["page"],
                "chunk_type": item["chunk_type"], "status": 1,
            })
            index += 1
    return chunks


# ---------- Chroma ----------

def _get_collection(kb: KBKnowledgeBase, create: bool = True):
    try:
        return CHROMA_CLIENT.get_collection(kb.collection_name)
    except Exception:
        if not create:
            return None
        return CHROMA_CLIENT.create_collection(
            kb.collection_name, metadata={"hnsw:space": "cosine", "dimension": kb.embedding_dimension}
        )


def upsert_vectors(kb: KBKnowledgeBase, chunks: list[dict]) -> None:
    """切片向量写入 Chroma（覆盖同 ID），metadata 带溯源与软删标记。"""
    if not chunks:
        return
    collection = _get_collection(kb)
    vectors = embed_texts([c["content"] for c in chunks], kb.embedding_dimension)
    ids = [f"f{c['file_id']}c{c['chunk_index']}" for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [
        {
            "kb_id": c["kb_id"], "file_id": c["file_id"], "chunk_index": c["chunk_index"],
            "title_path": c["title_path"] or "", "page": c["page"] or 0,
            "chunk_type": c["chunk_type"], "status": "active",
        }
        for c in chunks
    ]
    for i in range(0, len(ids), 100):
        collection.upsert(
            ids=ids[i:i + 100], embeddings=vectors[i:i + 100],
            documents=documents[i:i + 100], metadatas=metadatas[i:i + 100],
        )


def remove_file_vectors(kb: KBKnowledgeBase, file_id: int) -> None:
    """文件软删时同步移除其向量（collection 不存在则忽略）。"""
    collection = _get_collection(kb, create=False)
    if collection is not None:
        collection.delete(where={"file_id": file_id})


def retrieve(db: Session, *, query: str, kb_ids: list[int], top_k: int = 6) -> list[dict]:
    """跨库向量检索：按库各自的维度生成查询向量，过滤软删，按相似度合并排序。"""
    kbs = db.scalars(
        select(KBKnowledgeBase).where(KBKnowledgeBase.id.in_(kb_ids), KBKnowledgeBase.status != 2)
    ).all()
    if not kbs:
        raise HTTPException(status_code=422, detail="知识库不存在或已删除")

    results: list[dict] = []
    for kb in kbs:
        collection = _get_collection(kb, create=False)
        if collection is None:
            continue
        qv = embed_texts([query], kb.embedding_dimension)[0]
        res = collection.query(
            query_embeddings=[qv], n_results=top_k,
            where={"status": "active"},
            include=["documents", "metadatas", "distances"],
        )
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            results.append({
                "kb_id": kb.id, "kb_name": kb.name,
                "file_id": meta.get("file_id"), "chunk_index": meta.get("chunk_index"),
                "content": doc,
                "title_path": meta.get("title_path") or None,
                "page": meta.get("page") or None,
                "chunk_type": meta.get("chunk_type", "text"),
                "similarity": round(max(0.0, 1.0 - dist), 4),  # cosine 距离转相似度
            })

    # MySQL 侧兜底过滤（文件软删即不可引用）
    file_ids = {r["file_id"] for r in results if r["file_id"]}
    valid = set(
        db.scalars(select(KBFile.id).where(KBFile.id.in_(file_ids), KBFile.status != 2)).all()
    ) if file_ids else set()
    results = [r for r in results if r["file_id"] in valid]

    file_names = dict(
        db.execute(select(KBFile.id, KBFile.file_name).where(KBFile.id.in_(file_ids))).all()
    ) if file_ids else {}
    for r in results:
        r["file_name"] = file_names.get(r["file_id"], "")
    results.sort(key=lambda x: -x["similarity"])
    return results[:top_k]


def drop_kb_collection(kb: KBKnowledgeBase) -> None:
    """整库删除时移除 collection。"""
    try:
        CHROMA_CLIENT.delete_collection(kb.collection_name)
    except Exception:
        pass


def rebuild_kb_vectors(db: Session, kb: KBKnowledgeBase, operator: SysUser | None = None) -> dict:
    """按库重建向量索引：删除并重建 collection 后从 kb_chunk 全量重嵌入。"""
    drop_kb_collection(kb)
    chunks = db.scalars(
        select(KBChunk).where(KBChunk.kb_id == kb.id, KBChunk.status != 2).order_by(KBChunk.file_id, KBChunk.chunk_index)
    ).all()
    data = [
        {"file_id": c.file_id, "kb_id": c.kb_id, "chunk_index": c.chunk_index, "content": c.content,
         "title_path": c.title_path, "page": c.page, "chunk_type": c.chunk_type}
        for c in chunks
    ]
    for i in range(0, len(data), 256):
        upsert_vectors(kb, data[i:i + 256])
    write_log(db, user_id=operator.id if operator else None,
              username=operator.username if operator else "system", module="知识库",
              action="重建索引", params={"kb_id": kb.id, "chunks": len(data)}, result=1)
    return {"kb_id": kb.id, "chunks": len(data)}


# ---------- 异步入库任务 ----------

def process_file(file_id: int) -> None:
    """后台任务：待解析文件 → 解析 → 切分 → 向量化 → 双写。使用独立数据库会话。"""
    db = SessionLocal()
    try:
        kb_file = db.get(KBFile, file_id)
        if kb_file is None or kb_file.status == 2 or kb_file.parse_status not in (0, 3):
            return
        kb = db.get(KBKnowledgeBase, kb_file.kb_id)
        if kb is None or kb.status == 2:
            return

        kb_file.parse_status = 1
        kb_file.fail_reason = None
        db.commit()

        try:
            path = Path(settings.MEDIA_DIR) / kb_file.storage_path
            items = parse_file_to_items(kb_file.file_type, path)
            chunks = build_chunks(kb, kb_file.id, items)

            # 清空旧切片（重解析场景）
            for old in db.scalars(select(KBChunk).where(KBChunk.file_id == kb_file.id)).all():
                db.delete(old)
            db.flush()
            db.add_all([KBChunk(created_at=datetime.now(), **c) for c in chunks])
            kb_file.chunk_count = len(chunks)

            upsert_vectors(kb, chunks)
            kb_file.parse_status = 2
            db.commit()
        except Exception as exc:  # 记录失败原因，可重试
            db.rollback()
            kb_file = db.get(KBFile, file_id)
            kb_file.parse_status = 3
            kb_file.fail_reason = str(exc)[:250]
            db.commit()
    finally:
        db.close()
