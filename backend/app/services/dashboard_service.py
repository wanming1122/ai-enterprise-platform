"""工作台看板服务（M5-T1）：统计卡片与图表的只读聚合，不落任何业务数据。"""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance import AttRecord
from app.models.department import SysDepartment
from app.models.position import SysPosition
from app.models.salary import SalPayroll
from app.models.user import SysUser

# 考勤异常状态（与 att_rule 的 status_key 对应）
ABNORMAL_STATUSES = ("late", "early_leave", "miss_check", "absent")
ATT_STATUS_LABELS = {
    "normal": "正常",
    "late": "迟到",
    "early_leave": "早退",
    "miss_check": "漏打卡",
    "absent": "旷工",
    "leave": "请假",
    "business_trip": "出差",
}


def _month_range(d: date) -> tuple[date, date]:
    """返回所在月份的 [第一天, 下月第一天)。"""
    first = d.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt


def get_summary(db: Session) -> dict:
    today = date.today()
    month_first, month_next = _month_range(today)

    # ---------- 统计卡片 ----------
    # 与「各部门在职人数」图表同口径：只统计在职（status=1）账号，停用/待审批账号不计入
    user_count = db.scalar(select(func.count()).select_from(SysUser).where(SysUser.status == 1)) or 0
    dept_count = db.scalar(
        select(func.count()).select_from(SysDepartment).where(SysDepartment.status == 1)
    ) or 0
    position_count = db.scalar(
        select(func.count()).select_from(SysPosition).where(SysPosition.status == 1)
    ) or 0
    month_abnormal_count = db.scalar(
        select(func.count()).select_from(AttRecord).where(
            AttRecord.att_date >= month_first,
            AttRecord.att_date < month_next,
            AttRecord.status.in_(ABNORMAL_STATUSES),
        )
    ) or 0

    payroll_month = db.scalar(select(SalPayroll.year_month).order_by(SalPayroll.year_month.desc()).limit(1))
    payroll_count = 0
    payroll_total = 0.0
    if payroll_month:
        payroll_count = db.scalar(
            select(func.count()).select_from(SalPayroll).where(SalPayroll.year_month == payroll_month)
        ) or 0
        payroll_total = float(db.scalar(
            select(func.coalesce(func.sum(SalPayroll.total_salary), 0))
            .where(SalPayroll.year_month == payroll_month)
        ) or 0)

    # ---------- 部门人数分布（含 0 人部门；在职但未挂部门的账号归入「未分配部门」） ----------
    dept_rows = db.execute(
        select(SysDepartment.name, func.count(SysUser.id))
        .join(SysUser, (SysUser.department_id == SysDepartment.id) & (SysUser.status == 1), isouter=True)
        .where(SysDepartment.status == 1)
        .group_by(SysDepartment.id, SysDepartment.name)
        .order_by(func.count(SysUser.id).desc())
    ).all()
    dept_distribution = [{"name": name, "value": int(count)} for name, count in dept_rows]
    unassigned_count = db.scalar(
        select(func.count()).select_from(SysUser).where(SysUser.status == 1, SysUser.department_id.is_(None))
    ) or 0
    if unassigned_count:
        # 追加在末尾，保证真实部门保持人数降序
        dept_distribution.append({"name": "未分配部门", "value": int(unassigned_count)})

    # ---------- 职位人数 TOP8 ----------
    position_rows = db.execute(
        select(SysPosition.name, func.count(SysUser.id))
        .join(SysUser, (SysUser.position_id == SysPosition.id) & (SysUser.status == 1), isouter=True)
        .where(SysPosition.status == 1)
        .group_by(SysPosition.id, SysPosition.name)
        .order_by(func.count(SysUser.id).desc())
        .limit(8)
    ).all()
    position_distribution = [{"name": name, "value": int(count)} for name, count in position_rows]

    # ---------- 本月考勤状态分布 ----------
    status_rows = db.execute(
        select(AttRecord.status, func.count())
        .where(AttRecord.att_date >= month_first, AttRecord.att_date < month_next)
        .group_by(AttRecord.status)
    ).all()
    attendance_month_status = [
        {"name": ATT_STATUS_LABELS.get(status, status), "value": int(count)}
        for status, count in status_rows
    ]

    # ---------- 近6个月考勤异常趋势（含当月，往前推，补零保证连续） ----------
    months: list[str] = []
    for i in range(6):
        mm = today.month - 5 + i
        yy = today.year + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        months.append(f"{yy:04d}-{mm:02d}")
    trend_start = date(int(months[0][:4]), int(months[0][5:7]), 1)
    trend_rows = db.execute(
        select(func.date_format(AttRecord.att_date, "%Y-%m"), func.count())
        .where(
            AttRecord.att_date >= trend_start,
            AttRecord.att_date < month_next,
            AttRecord.status.in_(ABNORMAL_STATUSES),
        )
        .group_by(func.date_format(AttRecord.att_date, "%Y-%m"))
    ).all()
    trend_map = {month: int(count) for month, count in trend_rows}
    attendance_trend = [{"month": m, "value": trend_map.get(m, 0)} for m in months]

    return {
        "user_count": int(user_count),
        "dept_count": int(dept_count),
        "position_count": int(position_count),
        "month_abnormal_count": int(month_abnormal_count),
        "payroll_month": payroll_month,
        "payroll_count": payroll_count,
        "payroll_total": round(payroll_total, 2),
        "dept_distribution": dept_distribution,
        "position_distribution": position_distribution,
        "attendance_month_status": attendance_month_status,
        "attendance_trend": attendance_trend,
    }
