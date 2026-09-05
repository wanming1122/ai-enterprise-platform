"""考勤服务：记录查询、手动补录、Excel 导入（覆盖更新+错误行报告）与规则维护。"""
from datetime import date, datetime, time

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance import AttRecord, AttRule
from app.models.department import SysDepartment
from app.models.user import SysUser
from app.schemas.attendance import AttRecordCreate, AttRuleUpdate
from app.services.operation_log_service import write_log
from app.utils.excel import export_workbook, read_workbook

STATUS_LABELS = {
    "normal": "正常", "late": "迟到", "early_leave": "早退", "miss_check": "漏签",
    "absent": "旷工", "leave": "请假", "business_trip": "出差",
}
VALID_STATUS = set(STATUS_LABELS)

IMPORT_HEADERS = ["员工账号", "日期", "签到", "签退", "状态", "地点"]
SOURCE_TEXT = {1: "导入", 2: "手动"}


def _parse_date(value: str) -> date:
    """日期解析：兼容 YYYY-MM-DD / YYYY/M/D / 带时间部分的字符串。"""
    s = (value or "").strip()
    if " " in s:
        s = s.split(" ", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise HTTPException(status_code=422, detail="日期格式应为 YYYY-MM-DD")


def _parse_time(value: str | None) -> time | None:
    """时间解析：兼容 HH:MM / HH:MM:SS / 带日期前缀的字符串；空值为 None。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if " " in s:
        s = s.split(" ", 1)[1]
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise HTTPException(status_code=422, detail="时间格式应为 HH:MM 或 HH:MM:SS")


def _status_key(text: str) -> str | None:
    """状态解析：接受中文标签（迟到）或英文键（late）。"""
    s = (text or "").strip()
    if s in STATUS_LABELS.values():
        return next(k for k, v in STATUS_LABELS.items() if v == s)
    if s in VALID_STATUS:
        return s
    return None


def serialize_record(db: Session, r: AttRecord, users: dict[int, SysUser],
                     dept_names: dict[int, str]) -> dict:
    user = users.get(r.user_id)
    return {
        "id": r.id,
        "user_id": r.user_id,
        "username": user.username if user else None,
        "real_name": user.real_name if user else None,
        "dept_id": r.dept_id,
        "dept_name": dept_names.get(r.dept_id) if r.dept_id else None,
        "att_date": r.att_date.isoformat(),
        "check_in": r.check_in.strftime("%H:%M") if r.check_in else None,
        "check_out": r.check_out.strftime("%H:%M") if r.check_out else None,
        "status": r.status,
        "status_label": STATUS_LABELS.get(r.status, r.status),
        "location": r.location,
        "remark": r.remark,
        "source": r.source,
        "source_label": SOURCE_TEXT.get(r.source, ""),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def list_records(
    db: Session,
    *,
    department_id: int | None = None,
    user_id: int | None = None,
    month: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    q = select(AttRecord)
    if department_id:
        q = q.where(AttRecord.dept_id == department_id)
    if user_id:
        q = q.where(AttRecord.user_id == user_id)
    if month:
        try:
            month_start = datetime.strptime(month, "%Y-%m").date()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="月份格式应为 YYYY-MM") from exc
        if month_start.month == 12:
            next_month = date(month_start.year + 1, 1, 1)
        else:
            next_month = date(month_start.year, month_start.month + 1, 1)
        q = q.where(AttRecord.att_date >= month_start, AttRecord.att_date < next_month)
    if status:
        if status not in VALID_STATUS:
            raise HTTPException(status_code=422, detail="无效的考勤状态")
        q = q.where(AttRecord.status == status)

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    records = db.scalars(
        q.order_by(AttRecord.att_date.desc(), AttRecord.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()

    user_ids = {r.user_id for r in records}
    dept_ids = {r.dept_id for r in records if r.dept_id}
    users = {}
    dept_names = {}
    if user_ids:
        users = {u.id: u for u in db.scalars(select(SysUser).where(SysUser.id.in_(user_ids))).all()}
    if dept_ids:
        dept_names = dict(
            db.execute(select(SysDepartment.id, SysDepartment.name).where(SysDepartment.id.in_(dept_ids))).all()
        )
    return [serialize_record(db, r, users, dept_names) for r in records], total


def _upsert_record(
    db: Session, *, user: SysUser, att_date: date, check_in: time | None, check_out: time | None,
    status: str, location: str | None, remark: str | None, source: int, importer_id: int,
) -> tuple[AttRecord, bool]:
    """按 (user_id, att_date) 覆盖更新；返回 (记录, 是否覆盖已有记录)。"""
    record = db.scalar(
        select(AttRecord).where(AttRecord.user_id == user.id, AttRecord.att_date == att_date)
    )
    overwritten = record is not None
    if record is None:
        record = AttRecord(user_id=user.id, att_date=att_date)
        db.add(record)
    record.dept_id = user.department_id  # 部门快照取当前所属部门
    record.check_in = check_in
    record.check_out = check_out
    record.status = status
    record.location = location
    record.remark = remark
    record.source = source
    record.importer_id = importer_id
    db.flush()
    return record, overwritten


def create_manual(db: Session, data: AttRecordCreate, operator: SysUser) -> dict:
    """手动补录：同员工同日已有记录时覆盖更新。"""
    user = db.get(SysUser, data.user_id)
    if user is None or user.status == 2:
        raise HTTPException(status_code=422, detail="员工不存在")
    status = _status_key(data.status)
    if status is None:
        raise HTTPException(status_code=422, detail="无效的考勤状态")
    att_date = _parse_date(data.att_date)
    check_in = _parse_time(data.check_in)
    check_out = _parse_time(data.check_out)

    record, overwritten = _upsert_record(
        db, user=user, att_date=att_date, check_in=check_in, check_out=check_out,
        status=status, location=data.location, remark=data.remark,
        source=2, importer_id=operator.id,
    )
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="考勤管理",
              action="手动补录", params={**data.model_dump(), "overwritten": overwritten}, result=1)
    return {"id": record.id, "overwritten": overwritten}


def import_records(db: Session, file: UploadFile, operator: SysUser) -> dict:
    """Excel 导入：逐行校验，错误行跳过并报告；同员工同日重复行后者覆盖前者，与库内已有记录覆盖更新。"""
    content = file.file.read()
    rows = read_workbook(content, IMPORT_HEADERS)

    user_map = {u.username: u for u in db.scalars(select(SysUser).where(SysUser.status != 2)).all()}

    errors: list[dict] = []
    parsed: dict[tuple[int, date], dict] = {}  # (user_id, att_date) -> 行数据，同键后者覆盖
    for idx, row in enumerate(rows, start=2):
        username = row.get("员工账号", "")
        user = user_map.get(username)
        if user is None:
            errors.append({"row": idx, "reason": f"员工账号 {username} 不存在"})
            continue
        try:
            att_date = _parse_date(row.get("日期", ""))
        except HTTPException as exc:
            errors.append({"row": idx, "reason": f"日期无效：{exc.detail}"})
            continue
        status = _status_key(row.get("状态", ""))
        if status is None:
            errors.append({"row": idx, "reason": f"考勤状态 {row.get('状态', '')} 无效"})
            continue
        try:
            check_in = _parse_time(row.get("签到") or None)
            check_out = _parse_time(row.get("签退") or None)
        except HTTPException as exc:
            errors.append({"row": idx, "reason": f"时间无效：{exc.detail}"})
            continue
        parsed[(user.id, att_date)] = {
            "user": user, "att_date": att_date, "check_in": check_in, "check_out": check_out,
            "status": status, "location": row.get("地点") or None, "row": idx,
        }

    overwritten = 0
    existing_keys: set[tuple[int, date]] = set()
    if parsed:
        rows_ = db.execute(
            select(AttRecord.user_id, AttRecord.att_date).where(
                sa_or_keys(list(parsed.keys()))
            )
        ).all()
        existing_keys = {(r[0], r[1]) for r in rows_}
    for (uid, att_date), item in parsed.items():
        if (uid, att_date) in existing_keys:
            overwritten += 1
        _upsert_record(
            db, user=item["user"], att_date=item["att_date"], check_in=item["check_in"],
            check_out=item["check_out"], status=item["status"], location=item["location"],
            remark=None, source=1, importer_id=operator.id,
        )
    db.commit()

    write_log(db, user_id=operator.id, username=operator.username, module="考勤管理",
              action="导入考勤", params={"total": len(rows), "success": len(parsed),
                                         "failed": len(errors), "overwritten": overwritten}, result=1)
    return {
        "total": len(rows), "success": len(parsed), "failed": len(errors),
        "overwritten": overwritten, "errors": errors,
    }


def sa_or_keys(keys: list[tuple[int, date]]):
    """构造 (user_id, att_date) 组合的 OR 条件。"""
    from sqlalchemy import or_, and_
    return or_(*[and_(AttRecord.user_id == uid, AttRecord.att_date == d) for uid, d in keys])


def get_template() -> bytes:
    """导入模板：表头 + 示例行（状态列用中文）。"""
    rows = [
        ["zhangsan", "2026-09-01", "09:00", "18:00", "正常", "公司"],
        ["zhangsan", "2026-09-02", "09:25", "18:05", "迟到", "公司"],
        ["lisi", "2026-09-01", "", "18:00", "漏签", "公司"],
    ]
    return export_workbook(IMPORT_HEADERS, rows)


# ---------- 考勤规则维护 ----------

def serialize_rule(r: AttRule) -> dict:
    return {
        "id": r.id,
        "status_key": r.status_key,
        "status_label": STATUS_LABELS.get(r.status_key, r.status_key),
        "adjust_type": r.adjust_type,
        "amount": str(r.amount),
        "enabled": r.enabled,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def list_rules(db: Session) -> list[dict]:
    rules = db.scalars(select(AttRule).order_by(AttRule.id)).all()
    return [serialize_rule(r) for r in rules]


def update_rule(db: Session, rule_id: int, data: AttRuleUpdate, operator: SysUser) -> dict:
    rule = db.get(AttRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    updates = data.model_dump(exclude_unset=True)
    if "adjust_type" in updates and updates["adjust_type"] not in (1, 2):
        raise HTTPException(status_code=422, detail="调整类型应为 1奖励 或 2扣款")
    if "amount" in updates and updates["amount"] is not None and updates["amount"] < 0:
        raise HTTPException(status_code=422, detail="金额不能为负数")
    if "enabled" in updates and updates["enabled"] not in (0, 1):
        raise HTTPException(status_code=422, detail="启用状态应为 0 或 1")
    for field, value in updates.items():
        setattr(rule, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="考勤规则",
              action="编辑规则", params={"id": rule_id, **updates}, result=1)
    return serialize_rule(rule)
