"""用户管理路由：列表/新增/编辑/软删/启停/重置密码/Excel导入导出与模板。"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.user import UserCreate, UserUpdate
from app.services import user_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/users", tags=["用户管理"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/template")
def download_template(_: SysUser = Depends(require_permissions("user:import"))):
    """导入模板下载。"""
    return _xlsx_response(user_service.get_template(), "用户导入模板.xlsx")


@router.get("/export")
def export_users(
    keyword: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    role_id: int | None = Query(default=None),
    status: int | None = Query(default=None),
    _: SysUser = Depends(require_permissions("user:export")),
    db: Session = Depends(get_db),
):
    """按当前筛选条件导出用户。"""
    content = user_service.export_users(
        db, keyword=keyword, department_id=department_id, role_id=role_id, status=status
    )
    return _xlsx_response(content, "用户数据.xlsx")


@router.post("/import")
def import_users(
    file: UploadFile = File(...),
    operator: SysUser = Depends(require_permissions("user:import")),
    db: Session = Depends(get_db),
):
    """Excel 批量导入用户。"""
    if not (file.filename or "").endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="仅支持 .xlsx 文件")
    return ok(user_service.import_users(db, file, operator), message="导入完成")


@router.get("")
def list_users(
    keyword: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    role_id: int | None = Query(default=None),
    status: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("user:list")),
    db: Session = Depends(get_db),
):
    """用户分页列表（多条件筛选）。"""
    items, total = user_service.list_users(
        db, keyword=keyword, department_id=department_id, role_id=role_id,
        status=status, page=page, page_size=page_size,
    )
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_user(
    data: UserCreate,
    operator: SysUser = Depends(require_permissions("user:create")),
    db: Session = Depends(get_db),
):
    """新增用户。"""
    return ok(user_service.create_user(db, data, operator), message="新增成功")


@router.put("/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    operator: SysUser = Depends(require_permissions("user:update")),
    db: Session = Depends(get_db),
):
    """编辑用户。"""
    return ok(user_service.update_user(db, user_id, data, operator), message="编辑成功")


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    operator: SysUser = Depends(require_permissions("user:delete")),
    db: Session = Depends(get_db),
):
    """软删除用户。"""
    user_service.delete_user(db, user_id, operator)
    return ok(message="删除成功")


@router.put("/{user_id}/status")
def toggle_status(
    user_id: int,
    operator: SysUser = Depends(require_permissions("user:toggle")),
    db: Session = Depends(get_db),
):
    """启停账号。"""
    return ok(user_service.toggle_status(db, user_id, operator), message="操作成功")


@router.put("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    operator: SysUser = Depends(require_permissions("user:reset_pwd")),
    db: Session = Depends(get_db),
):
    """重置密码：返回临时密码，用户首次登录需修改。"""
    temp = user_service.reset_password(db, user_id, operator)
    return ok({"user_id": user_id, "temp_password": temp}, message=f"重置成功，临时密码：{temp}")
