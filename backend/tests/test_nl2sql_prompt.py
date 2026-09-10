"""NL2SQL 提示词约束与 0 行自纠回归测试（纯逻辑，不发起真实 LLM / 只读执行）。

背景：glm-4-flash 曾在生成 SQL 时把 sal_payroll.status（业务状态 0草稿/1已确认/2已发放）
误当软删除标记，自行添加 `WHERE status = 1`，导致演示数据（仅 0/2）返回 0 行，模型据此
回答"没有查询到"。修复：
1. 强化 NL2SQL 提示词：明确各表 status 语义，禁止添加无关 status 过滤，并给出正反示例。
2. `_tool_nl2sql` 在结果 0 行时追加自纠提示，借助 agent⇄tools 循环让模型去掉多余筛选重查。
"""
from app.models.user import SysUser
from app.services import ai_chat_service as S
from app.services import nl2sql_service as N


def test_system_prompt_forbids_unnecessary_status_filter():
    prompt = N._SYSTEM_PROMPT
    # 业务状态语义 + 硬性禁止
    assert "业务状态" in prompt
    assert "禁止添加任何 status 条件" in prompt
    # 正反示例：默认不加过滤；仅显式要求状态时才过滤
    assert "不要加 status 过滤" in prompt
    assert "已发放的工资单" in prompt


def test_table_ddl_documents_payroll_status_semantics():
    assert "非软删除标记" in N._TABLE_DDL


def _admin(db_session) -> SysUser:
    return db_session.query(SysUser).filter_by(username="admin").one()


def test_tool_nl2sql_zero_rows_hints_self_correction(monkeypatch, db_session):
    admin = _admin(db_session)
    monkeypatch.setattr(
        N, "generate_sql",
        lambda q: ("SELECT su.real_name FROM sal_payroll sp JOIN sys_user su ON sp.user_id=su.id "
                   "WHERE sp.total_salary=(SELECT MIN(total_salary) FROM sal_payroll WHERE status=1) LIMIT 1"),
    )
    monkeypatch.setattr(N, "execute_readonly", lambda sql: ([], 3))

    out = S._tool_nl2sql(db_session, {"user_id": admin.id, "username": admin.username}, "薪资最低的人是谁？")

    assert "共 0 行" in out
    # 0 行时应给出可执行的自纠提示
    assert "重新调用 nl2sql 查询一次" in out
    assert "status 过滤" in out


def test_tool_nl2sql_with_rows_has_no_self_correction_hint(monkeypatch, db_session):
    admin = _admin(db_session)
    monkeypatch.setattr(N, "generate_sql", lambda q: "SELECT 1 LIMIT 1")
    monkeypatch.setattr(N, "execute_readonly", lambda sql: ([{"real_name": "个人甲"}], 3))

    out = S._tool_nl2sql(db_session, {"user_id": admin.id, "username": admin.username}, "薪资最低的人是谁？")

    assert "共 1 行" in out
    assert "个人甲" in out
    assert "重新调用 nl2sql 查询一次" not in out
