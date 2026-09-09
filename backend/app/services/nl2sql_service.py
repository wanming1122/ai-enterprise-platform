"""NL2SQL 服务（M4-T2）：自然语言生成 SQL、安全双重校验、审核流与只读执行。

安全边界：仅一条以 SELECT 开头的语句、仅查 product 表（软删行 status=2 由
生成约束排除）、强制 LIMIT<=100；执行走独立只读连接（连接 5s / 读取 5s 超时，
会话级 READ ONLY + MAX_EXECUTION_TIME）。校验在生成入库前与执行前各跑一次。
"""
import json
import re
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.nl2sql import NL2SQLRecord
from app.models.user import SysUser
from app.schemas.nl2sql import NL2SQLGenerateIn, NL2SQLReviewIn
from app.services import llm_client
from app.services.operation_log_service import write_log

REVIEW_STATUS = {0: "待审核", 1: "通过", 2: "驳回", 3: "已执行"}
MAX_LIMIT = 100

# ---------- SQL 生成 ----------

_TABLE_DDL = (
    "product(id BIGINT 主键, name VARCHAR(64) 产品名称, category VARCHAR(32) 产品分类, "
    "price DECIMAL(10,2) 价格, stock INT 库存, description VARCHAR(255) 产品描述, "
    "status TINYINT 状态(1上架 0下架 2已删除), created_at DATETIME 创建时间, updated_at DATETIME 更新时间); "
    "sys_user(id BIGINT 主键, username VARCHAR(64) 登录账号, nickname VARCHAR(64) 昵称, "
    "real_name VARCHAR(64) 真实姓名, gender TINYINT 性别(0未知 1男 2女), "
    "email VARCHAR(128) 邮箱, phone VARCHAR(20) 手机号, "
    "department_id BIGINT 部门ID外键关联sys_department表, position_id BIGINT 职位ID外键关联sys_position表, "
    "status TINYINT 状态(1正常 0停用 2已删除), created_at DATETIME 创建时间); "
    "att_record(id BIGINT 主键, user_id BIGINT 员工ID外键关联sys_user表, dept_id BIGINT 部门快照, "
    "att_date DATE 考勤日期, check_in TIME 签到时间, check_out TIME 签退时间, "
    "status VARCHAR(16) 状态(normal正常/late迟到/early_leave早退/miss_check漏打卡/absent旷工/leave请假/business_trip出差), "
    "location VARCHAR(128) 考勤地点, remark VARCHAR(255) 备注, created_at DATETIME 创建时间); "
    "sal_payroll(id BIGINT 主键, user_id BIGINT 员工ID外键关联sys_user表, year_month VARCHAR(7) 月份YYYY-MM格式, "
    "position_name VARCHAR(64) 职位名称, base_salary DECIMAL(10,2) 基本工资, "
    "attendance_adjust DECIMAL(10,2) 考勤增减, manual_adjust DECIMAL(10,2) 手动奖惩, "
    "total_salary DECIMAL(10,2) 应发合计, status TINYINT 状态(0草稿 1已确认 2已发放), "
    "created_at DATETIME 创建时间)"
)

_ALLOWED_TABLES = {"product", "sys_user", "att_record", "sal_payroll"}

_SYSTEM_PROMPT = (
    "你是MySQL SQL生成器，只负责把用户的自然语言转换为一条SELECT查询语句。\n"
    f"可用表（共四张）：{_TABLE_DDL}\n"
    "严格要求：\n"
    "1. 只输出一条SELECT语句，必须以SELECT开头；禁止INSERT/UPDATE/DELETE/DDL等任何非查询语句。\n"
    "2. 只允许查询上述四张表（product/sys_user/att_record/sal_payroll），禁止访问其他表，禁止访问系统库。\n"
    "3. 可以使用JOIN关联上述四张表进行跨表查询，如：查询某部门的考勤记录可JOIN sys_user和att_record。\n"
    "4. 结果必须排除已删除数据：product表用status!=2，sys_user表用status!=2，其他表无软删除字段无需过滤。\n"
    "5. 语句必须以LIMIT结尾，且LIMIT返回行数不超过100。\n"
    "6. 不使用库名前缀限定列名，不使用注释，末尾不加分号。可以使用表别名。\n"
    "7. 只输出SQL文本本身：不要任何解释、不要markdown代码块围栏、不要多余字符。\n"
    "常见查询场景：\n"
    "- 产品库存/价格/分类 → 查询product表\n"
    "- 员工信息/部门/职位 → 查询sys_user表，可JOIN department和position\n"
    "- 考勤记录/迟到早退 → 查询att_record表，可JOIN sys_user获取员工信息\n"
    "- 工资单/薪资统计 → 查询sal_payroll表，可JOIN sys_user获取员工信息"
)


def generate_sql(question: str) -> str:
    """调生成模型产出 SQL 并安全校验/规整；模型未返回正文或不合法均 422。"""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"自然语言：{question}"},
    ]
    content = llm_client.chat_once(messages, max_tokens=2048, temperature=0.2)
    if not content:
        # 推理型模型可能在低 token 下只输出思考过程，加大配额重试一次
        content = llm_client.chat_once(messages, max_tokens=4096, temperature=0.2)
    if not content:
        raise HTTPException(status_code=422, detail="生成模型未返回SQL，请重试")
    return validate_and_normalize_sql(content)


# ---------- SQL 安全校验 ----------

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*(.*?)\s*```\s*$", re.S)
_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|set|use|"
    r"lock|unlock|load|handler|prepare|execute|exec|replace|rename|optimize|analyze|"
    r"repair|flush|shutdown|kill|into|outfile|dumpfile|sleep|benchmark|load_file|"
    r"for\s+update|for\s+share|information_schema|performance_schema|mysql|sys)\b",
    re.I,
)
_QUALIFIED_RE = re.compile(r"[a-zA-Z_]\s*\.\s*[\w*]")
_TABLE_REF_RE = re.compile(r"\b(from|join)\s+`?([a-zA-Z_]\w*)`?", re.I)
_LIMIT_TAIL_RE = re.compile(r"\blimit\s+(\d+)\s*(?:,\s*(\d+))?(?:\s+offset\s+(\d+))?\s*$", re.I)
_LIMIT_ANY_RE = re.compile(r"\blimit\s+\d+", re.I)


def _strip_literals(sql: str) -> str:
    """把 '...'/"..." 字符串字面量替换为空串，供关键词/对象扫描（不改原 SQL）。"""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"'):
            quote = ch
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:  # 双写转义
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            out.append("''")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _reject(detail: str) -> None:
    raise HTTPException(status_code=422, detail=detail)


def validate_and_normalize_sql(raw: str) -> str:
    """生成入库前/执行前共用的校验与规整：返回可直接执行的 SQL，不合法 422。"""
    sql = (raw or "").strip()
    fenced = _FENCE_RE.match(sql)
    if fenced:
        sql = fenced.group(1).strip()
    if not sql:
        _reject("生成内容为空，不是合法SQL")
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    if ";" in sql:
        _reject("仅允许单条SELECT语句（检测到分号多语句）")

    stripped = _strip_literals(sql)
    if re.search(r"--|#|/\*", stripped):
        _reject("SQL中不允许包含注释")
    if not re.match(r"^\s*select\b", stripped, re.I):
        _reject("仅允许SELECT查询语句，其他语句一律拒绝")
    bad = _FORBIDDEN_RE.search(stripped)
    if bad:
        _reject(f"SQL包含禁止的关键词或对象：{bad.group(0)}")
    if _QUALIFIED_RE.search(stripped):
        # 允许使用表别名，但不允许使用库名前缀
        # 检查是否有db.table格式的引用
        for match in re.finditer(r"([a-zA-Z_]\w*)\s*\.\s*([a-zA-Z_]\w*)", stripped):
            prefix = match.group(1).lower()
            # 如果前缀不是已知表名，则认为是库名前缀，拒绝
            if prefix not in _ALLOWED_TABLES and prefix not in {"p", "u", "a", "s"}:  # 允许常见别名
                _reject("不允许使用库名前缀限定（仅可查询product/sys_user/att_record/sal_payroll表）")

    tables = [name.lower() for _, name in _TABLE_REF_RE.findall(stripped)]
    if not tables:
        _reject("SQL中未发现查询的表")
    invalid_tables = [t for t in tables if t not in _ALLOWED_TABLES]
    if invalid_tables:
        _reject(f"禁止查询以下表：{', '.join(invalid_tables)}，仅允许查询product/sys_user/att_record/sal_payroll")

    tail = _LIMIT_TAIL_RE.search(sql)
    offset_any = re.search(r"\boffset\b", stripped, re.I)
    if tail is None and (_LIMIT_ANY_RE.search(stripped) or offset_any):
        _reject("LIMIT 仅允许出现在语句末尾且最多一次")
    if tail is None:
        sql = f"{sql} LIMIT {MAX_LIMIT}"
    else:
        # LIMIT off,cnt 取 cnt；LIMIT n [OFFSET m] 取 n，超过 100 改写为 100
        count_group = 2 if tail.group(2) is not None else 1
        if int(tail.group(count_group)) > MAX_LIMIT:
            start, end = tail.span(count_group)
            sql = sql[:start] + str(MAX_LIMIT) + sql[end:]
    return sql


# ---------- 只读执行 ----------

_readonly_engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 5, "read_timeout": 5},
)


def _run_readonly(sql: str) -> tuple[list[dict], int]:
    """独立只读连接执行 SELECT，返回 (行列表, 耗时ms)。"""
    with _readonly_engine.connect() as conn:
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        conn.rollback()
        conn.execute(text("SET SESSION MAX_EXECUTION_TIME=5000"))
        conn.rollback()
        start = time.perf_counter()
        try:
            rows = [dict(m) for m in conn.execute(text(sql)).mappings()]
        finally:
            conn.rollback()
    return rows, int((time.perf_counter() - start) * 1000)


def execute_readonly(sql: str) -> tuple[list[dict], int]:
    """只读执行的公开入口（AI助手 nl2sql 工具复用）。"""
    return _run_readonly(sql)


# ---------- 记录业务 ----------

def _get_record(db: Session, record_id: int) -> NL2SQLRecord:
    rec = db.get(NL2SQLRecord, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return rec


def _username(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    return db.scalar(select(SysUser.username).where(SysUser.id == user_id))


def _result_payload(rec: NL2SQLRecord) -> dict:
    return json.loads(rec.result_json) if rec.result_json else {"columns": [], "rows": []}


def serialize_record(rec: NL2SQLRecord, username: str | None = None, *, include_result: bool = False) -> dict:
    data = {
        "id": rec.id,
        "username": username,
        "question": rec.question,
        "generated_sql": rec.generated_sql,
        "review_status": rec.review_status,
        "review_status_label": REVIEW_STATUS.get(rec.review_status, "未知"),
        "review_comment": rec.review_comment,
        "reviewer_id": rec.reviewer_id,
        "result_count": len(_result_payload(rec)["rows"]) if rec.result_json else None,
        "execution_ms": rec.execution_ms,
        "executed_at": rec.executed_at.isoformat() if rec.executed_at else None,
        "created_at": rec.created_at.isoformat(),
    }
    if include_result:
        data["result"] = _result_payload(rec)
    return data


def list_records(
    db: Session, *, keyword: str | None = None, status: int | None = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[dict], int]:
    q = select(NL2SQLRecord, SysUser.username).outerjoin(SysUser, SysUser.id == NL2SQLRecord.user_id)
    if keyword:
        q = q.where(NL2SQLRecord.question.like(f"%{keyword}%"))
    if status is not None:
        q = q.where(NL2SQLRecord.review_status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.execute(
        q.order_by(NL2SQLRecord.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_record(rec, username) for rec, username in rows], total


def generate_record(db: Session, data: NL2SQLGenerateIn, operator: SysUser) -> dict:
    sql = generate_sql(data.question)
    rec = NL2SQLRecord(user_id=operator.id, question=data.question, generated_sql=sql, review_status=0)
    db.add(rec)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="NL2SQL",
              action="生成SQL", params={"question": data.question, "sql": sql}, result=1)
    return serialize_record(rec, operator.username)


def review_record(db: Session, record_id: int, data: NL2SQLReviewIn, operator: SysUser) -> dict:
    rec = _get_record(db, record_id)
    if rec.review_status != 0:
        raise HTTPException(status_code=422, detail="仅待审核记录可审核")
    rec.review_status = 1 if data.action == "approve" else 2
    rec.reviewer_id = operator.id
    rec.review_comment = data.comment
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="NL2SQL",
              action="审核通过" if data.action == "approve" else "审核驳回",
              params={"id": rec.id, "comment": data.comment}, result=1)
    return serialize_record(rec, _username(db, rec.user_id))


def execute_record(db: Session, record_id: int, operator: SysUser) -> dict:
    rec = _get_record(db, record_id)
    if rec.review_status == 3:
        raise HTTPException(status_code=422, detail="该记录已执行，禁止重复执行")
    if rec.review_status != 1:
        raise HTTPException(status_code=422, detail="仅审核通过的记录可执行")
    sql = validate_and_normalize_sql(rec.generated_sql)  # 执行前二次校验
    try:
        rows, ms = _run_readonly(sql)
    except SQLAlchemyError as exc:
        write_log(db, user_id=operator.id, username=operator.username, module="NL2SQL",
                  action="执行SQL", params={"id": rec.id}, result=0, error_message=str(exc)[:200])
        raise HTTPException(status_code=422, detail=f"SQL执行失败：{str(exc)[:200]}")
    payload = {"columns": list(rows[0].keys()) if rows else [], "rows": rows}
    # Decimal/datetime 统一转字符串，保证响应与落库 result_json 结构一致
    payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    rec.result_json = json.dumps(payload, ensure_ascii=False)
    rec.execution_ms = ms
    rec.executed_at = datetime.now()
    rec.review_status = 3
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="NL2SQL",
              action="执行SQL", params={"id": rec.id, "rows": len(rows), "ms": ms}, result=1)
    return serialize_record(rec, _username(db, rec.user_id), include_result=True)


def get_record_detail(db: Session, record_id: int) -> dict:
    rec = _get_record(db, record_id)
    return serialize_record(rec, _username(db, rec.user_id), include_result=True)
