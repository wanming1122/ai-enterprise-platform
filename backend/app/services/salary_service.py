"""薪资服务：按月生成工资单（职位基本工资+考勤增减+手动奖惩）、确认发放、奖惩录入。"""
from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance import AttRecord, AttRule
from app.models.department import SysDepartment
from app.models.position import SysPosition
from app.models.salary import SalAdjustment, SalPayroll
from app.models.user import SysUser
from app.schemas.salary import SalAdjustmentCreate, SalaryGenerate
from app.services.attendance_service import STATUS_LABELS
from app.services.operation_log_service import write_log

PAYROLL_STATUS = {0: "草稿", 1: "已确认", 2: "已发放"}
ADJUST_TYPE_TEXT = {1: "奖励", 2: "罚款"}


def _month_range(year_month: str) -> tuple[date, date]:
    """解析 YYYY-MM 为 [月初, 次月月初) 区间；格式非法抛 422。"""
    try:
        start = datetime.strptime(year_month, "%Y-%m").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="月份格式应为 YYYY-MM") from exc
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    return start, next_month


def _enabled_rules(db: Session) -> dict[str, tuple[int, Decimal]]:
    """启用中的考勤规则：status_key -> (adjust_type, amount)。"""
    rules = db.scalars(select(AttRule).where(AttRule.enabled == 1)).all()
    return {r.status_key: (r.adjust_type, r.amount) for r in rules}


def compute_attendance_items(db: Session, user_id: int, year_month: str) -> tuple[list[dict], Decimal]:
    """按月逐条计算考勤增减：迟到/早退/漏签按次、旷工按日（每条记录计一次）。"""
    start, end = _month_range(year_month)
    rules = _enabled_rules(db)
    records = db.scalars(
        select(AttRecord).where(
            AttRecord.user_id == user_id, AttRecord.att_date >= start, AttRecord.att_date < end
        ).order_by(AttRecord.att_date)
    ).all()
    items: list[dict] = []
    total = Decimal("0")
    for r in records:
        rule = rules.get(r.status)
        if rule is None:
            continue
        adjust_type, amount = rule
        delta = amount if adjust_type == 1 else -amount
        total += delta
        items.append({
            "att_date": r.att_date.isoformat(),
            "status": r.status,
            "status_label": STATUS_LABELS.get(r.status, r.status),
            "adjust_type": adjust_type,
            "amount": str(amount),
            "delta": str(delta),
        })
    return items, total


def compute_manual_items(db: Session, user_id: int, year_month: str) -> tuple[list[SalAdjustment], Decimal]:
    """归属该月的手动奖惩合计：奖励为正、罚款为负。"""
    adjustments = db.scalars(
        select(SalAdjustment).where(
            SalAdjustment.user_id == user_id, SalAdjustment.year_month == year_month
        ).order_by(SalAdjustment.id)
    ).all()
    total = Decimal("0")
    for a in adjustments:
        total += a.amount if a.adjust_type == 1 else -a.amount
    return list(adjustments), total


def serialize_payroll(db: Session, p: SalPayroll, users: dict[int, SysUser] | None = None,
                      dept_names: dict[int, str] | None = None) -> dict:
    if users is None:
        users = {p.user_id: db.get(SysUser, p.user_id)}  # type: ignore[dict-item]
    if dept_names is None:
        dept_names = {}
    user = users.get(p.user_id)
    return {
        "id": p.id,
        "user_id": p.user_id,
        "username": user.username if user else None,
        "real_name": user.real_name if user else None,
        "dept_name": dept_names.get(user.department_id) if user and user.department_id else None,
        "year_month": p.year_month,
        "position_name": p.position_name,
        "base_salary": str(p.base_salary),
        "attendance_adjust": str(p.attendance_adjust),
        "manual_adjust": str(p.manual_adjust),
        "total_salary": str(p.total_salary),
        "status": p.status,
        "status_label": PAYROLL_STATUS.get(p.status, ""),
        "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def generate_payrolls(db: Session, data: SalaryGenerate, operator: SysUser) -> dict:
    """按月生成/重算工资单：仅覆盖草稿，已确认/已发放锁定不重算。"""
    start, _ = _month_range(data.year_month)
    _ = start  # 仅校验格式

    q = select(SysUser).where(SysUser.status == 1, SysUser.position_id.is_not(None))
    if data.user_ids:
        q = q.where(SysUser.id.in_(data.user_ids))
    users = db.scalars(q).all()

    generated, locked, no_position = 0, 0, []
    for user in users:
        position = db.get(SysPosition, user.position_id)
        if position is None or position.status == 2:
            no_position.append(user.username)
            continue
        existing = db.scalar(
            select(SalPayroll).where(
                SalPayroll.user_id == user.id, SalPayroll.year_month == data.year_month
            )
        )
        if existing is not None and existing.status != 0:
            locked += 1
            continue

        _, att_total = compute_attendance_items(db, user.id, data.year_month)
        _, manual_total = compute_manual_items(db, user.id, data.year_month)
        total = position.base_salary + att_total + manual_total

        if existing is None:
            db.add(SalPayroll(
                user_id=user.id, year_month=data.year_month,
                position_name=position.name, base_salary=position.base_salary,
                attendance_adjust=att_total, manual_adjust=manual_total,
                total_salary=total, status=0, operator_id=operator.id,
            ))
        else:
            existing.position_name = position.name
            existing.base_salary = position.base_salary
            existing.attendance_adjust = att_total
            existing.manual_adjust = manual_total
            existing.total_salary = total
            existing.operator_id = operator.id
        generated += 1
    db.commit()

    write_log(db, user_id=operator.id, username=operator.username, module="薪资管理",
              action="生成工资单", params={
                  "year_month": data.year_month, "generated": generated,
                  "locked": locked, "no_position": no_position,
              }, result=1)
    return {"year_month": data.year_month, "generated": generated, "locked": locked,
            "no_position": no_position}


def list_payrolls(
    db: Session,
    *,
    year_month: str | None = None,
    department_id: int | None = None,
    user_id: int | None = None,
    status: int | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: SysUser | None = None,
) -> tuple[list[dict], int]:
    q = select(SalPayroll)

    # 应用数据范围权限
    if current_user:
        from app.core.deps import apply_data_scope
        q = apply_data_scope(q, SalPayroll, current_user, db, user_field="user_id")

    if year_month:
        _month_range(year_month)  # 格式校验
        q = q.where(SalPayroll.year_month == year_month)
    if user_id:
        q = q.where(SalPayroll.user_id == user_id)
    if status is not None:
        q = q.where(SalPayroll.status == status)
    if department_id:
        q = q.join(SysUser, SysUser.id == SalPayroll.user_id).where(SysUser.department_id == department_id)

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    payrolls = db.scalars(
        q.order_by(SalPayroll.year_month.desc(), SalPayroll.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()

    user_ids = {p.user_id for p in payrolls}
    users: dict[int, SysUser] = {}
    dept_names: dict[int, str] = {}
    if user_ids:
        users = {u.id: u for u in db.scalars(select(SysUser).where(SysUser.id.in_(user_ids))).all()}
        dept_ids = {u.department_id for u in users.values() if u.department_id}
        if dept_ids:
            dept_names = dict(
                db.execute(select(SysDepartment.id, SysDepartment.name).where(SysDepartment.id.in_(dept_ids))).all()
            )
    return [serialize_payroll(db, p, users, dept_names) for p in payrolls], total


def get_payroll(db: Session, payroll_id: int) -> SalPayroll:
    payroll = db.get(SalPayroll, payroll_id)
    if payroll is None:
        raise HTTPException(status_code=404, detail="工资单不存在")
    return payroll


def payroll_detail(db: Session, payroll_id: int) -> dict:
    """工资单明细：三项构成汇总（生成时快照）+ 考勤/奖惩逐条明细（按当前数据展示）。"""
    payroll = get_payroll(db, payroll_id)
    att_items, _ = compute_attendance_items(db, payroll.user_id, payroll.year_month)
    adjustments, _ = compute_manual_items(db, payroll.user_id, payroll.year_month)
    user = db.get(SysUser, payroll.user_id)
    return {
        "payroll": serialize_payroll(db, payroll, {payroll.user_id: user} if user else None),
        "attendance_items": att_items,
        "adjustment_items": [
            {
                "id": a.id, "adjust_type": a.adjust_type,
                "adjust_type_label": ADJUST_TYPE_TEXT.get(a.adjust_type, ""),
                "amount": str(a.amount), "reason": a.reason,
                "year_month": a.year_month,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in adjustments
        ],
    }


def confirm_payroll(db: Session, payroll_id: int, operator: SysUser) -> dict:
    payroll = get_payroll(db, payroll_id)
    if payroll.status != 0:
        raise HTTPException(status_code=422, detail="仅草稿状态的工资单可确认")
    payroll.status = 1
    payroll.confirmed_at = datetime.now()
    payroll.operator_id = operator.id
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="薪资管理",
              action="确认工资单", params={"id": payroll_id, "year_month": payroll.year_month}, result=1)
    return serialize_payroll(db, payroll)


def pay_payroll(db: Session, payroll_id: int, operator: SysUser) -> dict:
    payroll = get_payroll(db, payroll_id)
    if payroll.status != 1:
        raise HTTPException(status_code=422, detail="仅已确认的工资单可发放")
    payroll.status = 2
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="薪资管理",
              action="发放工资单", params={"id": payroll_id, "year_month": payroll.year_month}, result=1)
    return serialize_payroll(db, payroll)


# ---------- 手动奖惩 ----------

def serialize_adjustment(db: Session, a: SalAdjustment) -> dict:
    user = db.get(SysUser, a.user_id)
    return {
        "id": a.id,
        "user_id": a.user_id,
        "username": user.username if user else None,
        "real_name": user.real_name if user else None,
        "adjust_type": a.adjust_type,
        "adjust_type_label": ADJUST_TYPE_TEXT.get(a.adjust_type, ""),
        "amount": str(a.amount),
        "delta": str(a.amount if a.adjust_type == 1 else -a.amount),
        "reason": a.reason,
        "year_month": a.year_month,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def list_adjustments(
    db: Session,
    *,
    year_month: str | None = None,
    user_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: SysUser | None = None,
) -> tuple[list[dict], int]:
    q = select(SalAdjustment)

    # 应用数据范围权限
    if current_user:
        from app.core.deps import apply_data_scope
        q = apply_data_scope(q, SalAdjustment, current_user, db, user_field="user_id")

    if year_month:
        _month_range(year_month)
        q = q.where(SalAdjustment.year_month == year_month)
    if user_id:
        q = q.where(SalAdjustment.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    adjustments = db.scalars(
        q.order_by(SalAdjustment.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_adjustment(db, a) for a in adjustments], total


def create_adjustment(db: Session, data: SalAdjustmentCreate, operator: SysUser) -> dict:
    """奖惩录入：金额必须为正，方向由 adjust_type 决定。

    未填月份默认归属当前月（否则该记录永不进入任何工资单）；目标月份的工资单
    若已确认/已发放则拒绝录入——非草稿工资单重算会被跳过，追加记录会导致
    工资总额与明细永久不一致（金额静默丢失）。
    """
    user = db.get(SysUser, data.user_id)
    if user is None or user.status == 2:
        raise HTTPException(status_code=422, detail="员工不存在")
    if data.adjust_type not in (1, 2):
        raise HTTPException(status_code=422, detail="类型应为 1奖励 或 2罚款")
    if data.amount <= 0:
        raise HTTPException(status_code=422, detail="金额必须大于0")
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=422, detail="事由不能为空")
    if not data.year_month:
        data.year_month = datetime.now().strftime("%Y-%m")
    _month_range(data.year_month)
    payroll = db.scalar(
        select(SalPayroll).where(
            SalPayroll.user_id == data.user_id, SalPayroll.year_month == data.year_month
        )
    )
    if payroll is not None and payroll.status != 0:
        label = PAYROLL_STATUS.get(payroll.status, "已锁定")
        raise HTTPException(
            status_code=422,
            detail=f"{data.year_month} 工资单已「{label}」，不可追加奖惩；如需调整请先生成草稿重算",
        )
    adjustment = SalAdjustment(
        user_id=data.user_id, adjust_type=data.adjust_type,
        amount=Decimal(str(data.amount)), reason=data.reason.strip(),
        year_month=data.year_month, operator_id=operator.id,
    )
    db.add(adjustment)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="薪资管理",
              action="奖惩录入", params=data.model_dump(), result=1)
    return serialize_adjustment(db, adjustment)
