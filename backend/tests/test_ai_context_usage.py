"""上下文统计真实性相关（D + A + C）回归测试。

- A：模型配置未填 context_window 时按模型名推断，避免回落到 32K 全局常量导致占比虚高。
- D：打开历史会话时优先使用最近一轮落库的真实占用（usage.context_tokens），缺失才退回估算。
- C：缓存命中率随 usage 落库，打开会话时一并返回。

纯逻辑测试：直接构造 AIMessage 内存对象，不发起数据库/网络请求。
"""
from app.models.ai import AIMessage
from app.services import ai_chat_service as S
from app.services import ai_model_service as M


# ---------- A：上下文窗口推断 ----------


def test_infer_context_window_prefers_configured():
    assert M.infer_context_window("glm-4-flash", 64000) == 64000


def test_infer_context_window_by_model_name():
    assert M.infer_context_window("glm-4.7-flash", None) == 128000
    assert M.infer_context_window("glm-4-flash", None) == 128000
    assert M.infer_context_window("GLM-5.3-Flash", None) == 128000


def test_infer_context_window_unknown_returns_none():
    assert M.infer_context_window("some-unknown-model", None) is None
    assert M.infer_context_window(None, None) is None


# ---------- D / C：打开会话的上下文与缓存命中率 ----------


def _msg(role: str, content: str, usage: dict | None = None) -> AIMessage:
    return AIMessage(conversation_id=1, role=role, content=content, usage=usage)


def test_conversation_context_prefers_real_tokens():
    msgs = [
        _msg("user", "薪资最低的人是谁？"),
        _msg(
            "assistant", "个人甲",
            usage={"prompt_tokens": 3000, "context_tokens": 2880, "cache_hit_rate": 0.42},
        ),
    ]
    ctx = S._estimate_conversation_context(msgs)
    # 用真实单次最大 prompt（2880），而非全轮累加的计费口径（3000）
    assert ctx["total"] == 2880
    # 分项按比例缩放，合计与真实占用一致（允许逐项四舍五入误差）
    assert abs(sum(b["tokens"] for b in ctx["breakdown"]) - 2880) <= len(ctx["breakdown"])
    assert ctx["cache_hit_rate"] == 0.42


def test_conversation_context_falls_back_when_no_usage():
    ctx = S._estimate_conversation_context([_msg("assistant", "答案", usage=None)])
    assert ctx["total"] > 0
    assert ctx["cache_hit_rate"] is None


def test_conversation_context_keeps_zero_rows():
    """无工具结果时应保持 0（此前 max(1,…) 会把 0 兜底成 1，导致浮层出现「工具结果 1」假象）。"""
    msgs = [_msg("assistant", "答案", usage={"context_tokens": 3000})]
    ctx = S._estimate_conversation_context(msgs)
    rows = {b["label"]: b["tokens"] for b in ctx["breakdown"]}
    assert rows["工具结果"] == 0
    # 分项缩放后合计仍与真实占用一致（允许逐项四舍五入误差）
    assert abs(sum(rows.values()) - ctx["total"]) <= len(rows)


def test_conversation_context_ignores_legacy_accumulated_prompt():
    """旧数据只有 prompt_tokens（累加口径）而无 context_tokens → 退回估算，避免高估。"""
    ctx = S._estimate_conversation_context([_msg("assistant", "答案", usage={"prompt_tokens": 999999})])
    assert 0 < ctx["total"] < 999999
    assert ctx["cache_hit_rate"] is None
