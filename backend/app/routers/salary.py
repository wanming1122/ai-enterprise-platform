"""薪资管理路由：工资单生成/查询/明细/确认/发放与手动奖惩。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.salary import SalAdjustmentCreate, SalaryGenerate
from app.services import salary_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/salaries", tags=["薪资管理"])


@router.get("/adjustments")
def list_adjustments(
    year_month: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: SysUser = Depends(require_permissions("salary:list")),
    db: Session = Depends(get_db),
):
    """手动奖惩分页列表。"""
    items, total = salary_service.list_adjustments(
        db, year_month=year_month, user_id=user_id, page=page, page_size=page_size,
        current_user=current_user,
    )
    return ok(page_result(items, total, page, page_size))


@router.post("/adjustments")
def create_adjustment(
    data: SalAdjustmentCreate,
    operator: SysUser = Depends(require_permissions("salary:adjust")),
    db: Session = Depends(get_db),
):
    """手动奖惩录入（奖励/罚款，须填写事由）。"""
    return ok(salary_service.create_adjustment(db, data, operator), message="录入成功")


@router.post("/generate")
def generate_payrolls(
    data: SalaryGenerate,
    operator: SysUser = Depends(require_permissions("salary:generate")),
    db: Session = Depends(get_db),
):
    """按月生成/重算工资单（仅草稿可重算，已确认/已发放锁定）。"""
    return ok(salary_service.generate_payrolls(db, data, operator), message="生成完成")


@router.get("")
def list_payrolls(
    year_month: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
    status: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: SysUser = Depends(require_permissions("salary:list")),
    db: Session = Depends(get_db),
):
    """工资单分页列表。"""
    items, total = salary_service.list_payrolls(
        db, year_month=year_month, department_id=department_id, user_id=user_id,
        status=status, page=page, page_size=page_size,
        current_user=current_user,
    )
    return ok(page_result(items, total, page, page_size))


@router.get("/{payroll_id}")
def payroll_detail(
    payroll_id: int,
    _: SysUser = Depends(require_permissions("salary:list")),
    db: Session = Depends(get_db),
):
    """工资单明细：三项构成与考勤/奖惩逐条明细。"""
    return ok(salary_service.payroll_detail(db, payroll_id))


@router.put("/{payroll_id}/confirm")
def confirm_payroll(
    payroll_id: int,
    operator: SysUser = Depends(require_permissions("salary:confirm")),
    db: Session = Depends(get_db),
):
    """确认工资单（草稿 → 已确认，锁定不再重算）。"""
    return ok(salary_service.confirm_payroll(db, payroll_id, operator), message="确认成功")


@router.put("/{payroll_id}/pay")
def pay_payroll(
    payroll_id: int,
    operator: SysUser = Depends(require_permissions("salary:pay")),
    db: Session = Depends(get_db),
):
    """发放工资单（已确认 → 已发放）。"""
    return ok(salary_service.pay_payroll(db, payroll_id, operator), message="发放成功")
