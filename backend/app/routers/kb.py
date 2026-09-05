"""知识库路由（M3-T1）：库 CRUD/软删、文件上传/列表/详情/软删/切片预览。

检索与问答接口在 M3-T3 增加。
"""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.kb import KBCreate, KBUpdate
from app.services import kb_service
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
    """软删除知识库及其下全部文件。"""
    kb_service.delete_kb(db, kb_id, operator)
    return ok(message="删除成功")


@router.post("/bases/{kb_id}/files")
def upload_file(
    kb_id: int,
    file: UploadFile = File(...),
    operator: SysUser = Depends(require_permissions("file:upload")),
    db: Session = Depends(get_db),
):
    """上传文件到知识库（校验后落盘待解析，M3-T2 接管解析入库）。"""
    kb = kb_service.get_kb(db, kb_id)
    return ok(kb_service.upload_file(db, kb, file, operator), message="上传成功")


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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("file:list")),
    db: Session = Depends(get_db),
):
    """切片分页预览：内容、标题路径、页码。"""
    items, total = kb_service.list_chunks(db, file_id, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    operator: SysUser = Depends(require_permissions("file:delete")),
    db: Session = Depends(get_db),
):
    """软删除文件（MySQL 与 Chroma 双侧标记）。"""
    kb_service.delete_file(db, file_id, operator)
    return ok(message="删除成功")
