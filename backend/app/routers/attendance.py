"""考勤管理路由：记录查询/手动补录/Excel导入与模板/规则维护。"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.attendance import AttRecordCreate, AttRuleUpdate
from app.services import attendance_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/attendances", tags=["考勤管理"])
rule_router = APIRouter(prefix="/api/v1/attendance-rules", tags=["考勤规则"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/template")
def download_template(_: SysUser = Depends(require_permissions("attendance:import"))):
    """导入模板下载。"""
    return _xlsx_response(attendance_service.get_template(), "考勤导入模板.xlsx")


@router.post("/import")
def import_records(
    file: UploadFile = File(...),
    operator: SysUser = Depends(require_permissions("attendance:import")),
    db: Session = Depends(get_db),
):
    """Excel 批量导入考勤：逐行校验，同员工同日重复导入覆盖更新。"""
    if not (file.filename or "").endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="仅支持 .xlsx 文件")
    return ok(attendance_service.import_records(db, file, operator), message="导入完成")


@router.get("")
def list_records(
    department_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
    month: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("attendance:list")),
    db: Session = Depends(get_db),
):
    """考勤记录分页列表（按部门/员工/月份/状态筛选）。"""
    items, total = attendance_service.list_records(
        db, department_id=department_id, user_id=user_id, month=month,
        status=status, page=page, page_size=page_size,
    )
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_record(
    data: AttRecordCreate,
    operator: SysUser = Depends(require_permissions("attendance:create")),
    db: Session = Depends(get_db),
):
    """手动补录考勤（同员工同日已有记录时覆盖更新）。"""
    return ok(attendance_service.create_manual(db, data, operator), message="补录成功")


@rule_router.get("")
def list_rules(
    _: SysUser = Depends(require_permissions("attendance_rule:list")),
    db: Session = Depends(get_db),
):
    """考勤薪资规则列表（固定 7 条）。"""
    return ok(attendance_service.list_rules(db))


@rule_router.put("/{rule_id}")
def update_rule(
    rule_id: int,
    data: AttRuleUpdate,
    operator: SysUser = Depends(require_permissions("attendance_rule:update")),
    db: Session = Depends(get_db),
):
    """编辑考勤规则（金额/调整类型/启用）。"""
    return ok(attendance_service.update_rule(db, rule_id, data, operator), message="保存成功")
