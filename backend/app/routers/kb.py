"""知识库路由：库管理、文件管理（T1/T2）与检索调试、SSE 问答、会话历史（T3）。"""
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.kb import KBChatIn, KBCreate, KBSearchIn, KBUpdate
from app.services import kb_chat_service, kb_rag_service, kb_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/kb", tags=["知识库"])


@router.get("/bases")
def list_kbs(
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("kb:list")),
    db: Session = Depends(get_db),
):
    """知识库分页列表。"""
    items, total = kb_service.list_kbs(db, keyword=keyword, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.post("/bases")
def create_kb(
    data: KBCreate,
    operator: SysUser = Depends(require_permissions("kb:create")),
    db: Session = Depends(get_db),
):
    """新建知识库（锁定 Embedding 模型与维度、切分参数）。"""
    return ok(kb_service.create_kb(db, data, operator), message="创建成功")


@router.get("/bases/{kb_id}")
def kb_detail(
    kb_id: int,
    _: SysUser = Depends(require_permissions("kb:list")),
    db: Session = Depends(get_db),
):
    """知识库详情（含文件数/切片数统计）。"""
    return ok(kb_service.serialize_kb(db, kb_service.get_kb(db, kb_id)))


@router.put("/bases/{kb_id}")
def update_kb(
    kb_id: int,
    data: KBUpdate,
    operator: SysUser = Depends(require_permissions("kb:update")),
    db: Session = Depends(get_db),
):
    """编辑知识库（模型与维度不可改）。"""
    return ok(kb_service.update_kb(db, kb_id, data, operator), message="保存成功")


@router.delete("/bases/{kb_id}")
def delete_kb(
    kb_id: int,
    operator: SysUser = Depends(require_permissions("kb:delete")),
    db: Session = Depends(get_db),
):
    """软删除知识库及其下全部文件（同步移除 Chroma collection）。"""
    kb = kb_service.get_kb(db, kb_id)
    kb_service.delete_kb(db, kb_id, operator)
    kb_rag_service.drop_kb_collection(kb)
    return ok(message="删除成功")


@router.post("/bases/{kb_id}/rebuild")
def rebuild_kb(
    kb_id: int,
    operator: SysUser = Depends(require_permissions("kb:update")),
    db: Session = Depends(get_db),
):
    """重建向量索引：删除并重建 collection 后从 MySQL 切片全量重嵌入。"""
    kb = kb_service.get_kb(db, kb_id)
    return ok(kb_rag_service.rebuild_kb_vectors(db, kb, operator), message="重建完成")


@router.post("/bases/{kb_id}/files")
def upload_file(
    kb_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    operator: SysUser = Depends(require_permissions("file:upload")),
    db: Session = Depends(get_db),
):
    """上传文件到知识库：校验落盘后异步解析入库。"""
    kb = kb_service.get_kb(db, kb_id)
    data = kb_service.upload_file(db, kb, file, operator)
    background_tasks.add_task(kb_rag_service.process_file, data["id"])
    return ok(data, message="上传成功，解析中")


@router.get("/bases/{kb_id}/files")
def list_files(
    kb_id: int,
    parse_status: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("file:list")),
    db: Session = Depends(get_db),
):
    """知识库文件分页列表（可按解析状态筛选）。"""
    items, total = kb_service.list_files(db, kb_id, parse_status=parse_status, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.get("/files/{file_id}")
def file_detail(
    file_id: int,
    _: SysUser = Depends(require_permissions("file:list")),
    db: Session = Depends(get_db),
):
    """文件详情：解析状态、切片数、失败原因。"""
    return ok(kb_service.serialize_file(kb_service.get_file(db, file_id)))


@router.get("/files/{file_id}/chunks")
def file_chunks(
    file_id: int,
    keyword: str | None = Query(default=None, description="按切片正文模糊过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("file:list")),
    db: Session = Depends(get_db),
):
    """切片分页预览：内容、标题路径、页码；可按关键词过滤。"""
    items, total = kb_service.list_chunks(db, file_id, keyword=keyword, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    operator: SysUser = Depends(require_permissions("file:delete")),
    db: Session = Depends(get_db),
):
    """软删除文件（MySQL 与 Chroma 双侧标记）。"""
    kb_file = kb_service.get_file(db, file_id)
    kb = kb_service.get_kb(db, kb_file.kb_id)
    kb_service.delete_file(db, file_id, operator)
    kb_rag_service.remove_file_vectors(kb, file_id)
    return ok(message="删除成功")


@router.post("/files/{file_id}/reparse")
def reparse_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    operator: SysUser = Depends(require_permissions("file:reparse")),
    db: Session = Depends(get_db),
):
    """重新解析：清空原切片后重跑入库链路。"""
    kb_file = kb_service.get_file(db, file_id)
    if kb_file.parse_status == 1:
        raise HTTPException(status_code=422, detail="文件正在解析中，请稍后再试")
    kb_file.parse_status = 0
    kb_file.fail_reason = None
    db.commit()
    background_tasks.add_task(kb_rag_service.process_file, file_id)
    return ok(message="已加入解析队列")


# ---------- 检索与问答（M3-T3） ----------

@router.post("/search")
def search(
    data: KBSearchIn,
    operator: SysUser = Depends(require_permissions("kb:search")),
    db: Session = Depends(get_db),
):
    """检索调试：query + kb_ids + top_k，返回切片、相似度与溯源信息。"""
    return ok(kb_chat_service.search_debug(
        db, operator, query=data.query, kb_ids=data.kb_ids, top_k=data.top_k
    ))


@router.post("/chat")
def chat(
    data: KBChatIn,
    operator: SysUser = Depends(require_permissions("kb:chat")),
    db: Session = Depends(get_db),
):
    """知识库问答：SSE 流式（message/reasoning → citations → done），支持多轮。"""
    kb_chat_service.validate_kbs(db, data.kb_ids)  # 流式开启前校验
    return StreamingResponse(
        kb_chat_service.chat_sse(
            operator.id, operator.username, question=data.question,
            kb_ids=data.kb_ids, conversation_id=data.conversation_id, top_k=data.top_k,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    operator: SysUser = Depends(require_permissions("kb:chat")),
    db: Session = Depends(get_db),
):
    """我的问答会话列表。"""
    items, total = kb_chat_service.list_conversations(db, operator, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.get("/conversations/{conversation_id}")
def conversation_detail(
    conversation_id: int,
    operator: SysUser = Depends(require_permissions("kb:chat")),
    db: Session = Depends(get_db),
):
    """会话历史（仅本人会话）。"""
    return ok(kb_chat_service.conversation_detail(db, operator, conversation_id))
