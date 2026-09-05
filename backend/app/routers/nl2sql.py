"""NL2SQL 路由（M4-T2）：生成、记录列表、审核、执行、查询历史。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.nl2sql import NL2SQLGenerateIn, NL2SQLReviewIn
from app.services import nl2sql_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/nl2sql", tags=["NL2SQL"])


@router.post("/generate")
def generate(
    data: NL2SQLGenerateIn,
    operator: SysUser = Depends(require_permissions("nl2sql:generate")),
    db: Session = Depends(get_db),
):
    """自然语言生成 SQL（校验通过后落库为待审核记录；不合法直接 422 不落库）。"""
    return ok(nl2sql_service.generate_record(db, data, operator), message="生成成功")


@router.get("/records")
def list_records(
    keyword: str | None = Query(default=None),
    status: int | None = Query(default=None, ge=0, le=3),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("nl2sql:generate")),
    db: Session = Depends(get_db),
):
    """记录分页列表（NL2SQL 主页面工作区，可按审核状态筛选）。"""
    items, total = nl2sql_service.list_records(
        db, keyword=keyword, status=status, page=page, page_size=page_size
    )
    return ok(page_result(items, total, page, page_size))


@router.get("/history")
def list_history(
    keyword: str | None = Query(default=None),
    status: int | None = Query(default=None, ge=0, le=3),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("nl2sql:history")),
    db: Session = Depends(get_db),
):
    """查询历史分页列表。"""
    items, total = nl2sql_service.list_records(
        db, keyword=keyword, status=status, page=page, page_size=page_size
    )
    return ok(page_result(items, total, page, page_size))


@router.get("/records/{record_id}")
def get_record(
    record_id: int,
    _: SysUser = Depends(require_permissions("nl2sql:history")),
    db: Session = Depends(get_db),
):
    """记录详情（含完整执行结果）。"""
    return ok(nl2sql_service.get_record_detail(db, record_id))


@router.post("/records/{record_id}/review")
def review_record(
    record_id: int,
    data: NL2SQLReviewIn,
    operator: SysUser = Depends(require_permissions("nl2sql:review")),
    db: Session = Depends(get_db),
):
    """审核：仅待审核记录可通过/驳回，意见可选。"""
    return ok(nl2sql_service.review_record(db, record_id, data, operator), message="审核完成")


@router.post("/records/{record_id}/execute")
def execute_record(
    record_id: int,
    operator: SysUser = Depends(require_permissions("nl2sql:execute")),
    db: Session = Depends(get_db),
):
    """执行：仅审核通过可执行，只读连接超时5秒，结果与耗时写回并置为已执行。"""
    return ok(nl2sql_service.execute_record(db, record_id, operator), message="执行成功")
