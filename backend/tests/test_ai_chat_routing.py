"""AI 助手 generate 空回答回归测试（纯逻辑，不发起真实 LLM / 数据库请求）。

背景：GLM-4-Flash 在 generate 阶段收到「以 assistant 结尾」的消息列表时，会认为该轮
已结束而返回空正文，导致"本次未生成有效回答"。修复分两处：

1. `_route_after_agent`：agent 已作答且无需注入知识库正文（context_chunks 为空）时直接
   走 direct，省掉多余的二次 LLM 调用；有检索正文仍需走 generate 注入。
2. `_generate_node`：组请求前剔除末尾「纯文本 assistant 终答」，保证请求不以 assistant 结尾
   （保留 assistant.tool_calls 与 tool 结果配对）。
"""
import asyncio

from app.services import ai_chat_service as S


# ---------- 路由决策 ----------


def test_route_after_agent_tool_calls_to_tools():
    state = {
        "messages": [{"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]}],
    }
    assert S._route_after_agent(state) == "tools"


def test_route_after_agent_nl2sql_answer_goes_direct():
    """nl2sql/server_admin 结果已在 tool 消息内：agent 已作答且无检索正文 → 直接下发。"""
    state = {
        "messages": [{"role": "assistant", "content": "薪资最高的是刘洋"}],
        "tool_trace": [{"tool": "nl2sql", "args": {}}],
        "context_chunks": [],
    }
    assert S._route_after_agent(state) == "direct"


def test_route_after_agent_with_retrieved_context_goes_generate():
    """知识库正文在 context_chunks（agent 不可见）→ 必须 generate 注入后再作答。"""
    state = {
        "messages": [{"role": "assistant", "content": "年假 5 天"}],
        "tool_trace": [{"tool": "retrieve", "args": {}}],
        "context_chunks": [{"file_name": "员工手册", "content": "年假 5 天"}],
    }
    assert S._route_after_agent(state) == "generate"


def test_route_after_agent_no_content_goes_generate():
    state = {"messages": [{"role": "assistant", "content": "   "}], "tool_trace": []}
    assert S._route_after_agent(state) == "generate"


# ---------- generate 请求消息规范化 ----------


def _tool_call_msg() -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "nl2sql", "arguments": '{"question": "薪资最高"}'},
        }],
    }


def test_generate_node_request_not_ended_with_assistant(monkeypatch):
    """回归：请求以 assistant 结尾会触发 GLM 空正文，必须剔除末尾纯文本终答。"""
    captured: dict = {}

    async def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        yield "content", "薪资最高的是刘洋，应发合计 15000.00 元。"

    monkeypatch.setattr(S.llm_client, "achat_stream", fake_stream)
    monkeypatch.setattr(S, "get_stream_writer", lambda: (lambda _ev: None))

    state = {
        "messages": [
            {"role": "system", "content": "AGENT SYSTEM"},
            {"role": "user", "content": "薪资最低的人是谁？"},
            {"role": "assistant", "content": "[此前工具结果] … 薪资最低的是刘洋"},
            {"role": "user", "content": "薪资最高的人是谁？"},
            _tool_call_msg(),
            {"role": "tool", "tool_call_id": "call_1", "content": "结果 JSON"},
            # agent 在 loop 中已产出的终答：generate 前会累积进 messages，正是空回答的诱因
            {"role": "assistant", "content": "薪资最高的人是刘洋，应发合计 15000.00 元。"},
        ],
        "context_chunks": [],
        "deep_thinking": False,
        "model_id": None,
    }

    result = asyncio.run(S._generate_node(state))
    msgs = captured["messages"]

    # 请求不得以 assistant 结尾（末尾应为 tool 结果消息）
    assert msgs[-1].get("role") == "tool"
    # assistant.tool_calls 与 tool 结果配对必须保留
    assert any(m.get("tool_calls") for m in msgs)
    # 末尾「纯文本 assistant 终答」已被剔除
    assert all(m.get("content") != "薪资最高的人是刘洋，应发合计 15000.00 元。" for m in msgs)
    # 历史中的 assistant 轮次（[此前工具结果]…）仍保留，仅剔除尾部终答
    assert any(m.get("role") == "assistant" and not m.get("tool_calls") for m in msgs)
    # 正常产出正文
    assert result["answer"] == "薪资最高的是刘洋，应发合计 15000.00 元。"


def test_generate_node_keeps_tool_pair_when_no_trailing_answer(monkeypatch):
    """没有末尾终答时不应误删 tool 配对，且首条为 generate 的 system 提示。"""
    captured: dict = {}

    async def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        yield "content", "ok"

    monkeypatch.setattr(S.llm_client, "achat_stream", fake_stream)
    monkeypatch.setattr(S, "get_stream_writer", lambda: (lambda _ev: None))

    state = {
        "messages": [
            {"role": "system", "content": "AGENT SYSTEM"},
            {"role": "user", "content": "薪资最高的人是谁？"},
            _tool_call_msg(),
            {"role": "tool", "tool_call_id": "call_1", "content": "结果 JSON"},
        ],
        "context_chunks": [],
        "deep_thinking": False,
        "model_id": None,
    }

    asyncio.run(S._generate_node(state))
    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "tool"
    assert any(m.get("tool_calls") for m in msgs)
