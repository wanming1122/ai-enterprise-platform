"""AI助手服务（M4-T3）：LangGraph Agent 问答，SSE 流式输出，会话与消息持久化。

图结构（设计方案 11.7）：agent 节点做工具调用决策 ⇄ tools 节点（retrieve 知识库检索、
nl2sql 产品数据查询）循环，决策完成后进入 generate 节点以 SSE 流式输出并附引用。
LLM 调用统一走 llm_client（httpx 直连 OpenAI 兼容接口）：推理型模型回放 tool_calls
必须携带 reasoning_content，由 chat_with_tools 返回的 dict 原样回放满足。
事件协议与 kb_chat_service 对齐：meta/tool/reasoning/message/citations/done/error。
"""
import json
import operator
import re
from datetime import datetime
from typing import Annotated, Literal, TypedDict

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from app.models.ai import AIConversation, AIMessage
from app.models.kb import KBKnowledgeBase
from app.models.nl2sql import NL2SQLRecord
from app.services import kb_rag_service, llm_client, nl2sql_service, server_admin_service
from app.services.operation_log_service import write_log
from app.db.session import SessionLocal

HISTORY_ROUNDS = 4          # 多轮上下文回放最近 4 轮 user/assistant 终答
MAX_TOOL_ROUNDS = 6         # 单次提问工具调用轮次上限
TOOL_RESULT_MAX_CHARS = 4000
TOOL_STORE_MAX_CHARS = 2000  # tool 消息持久化截断长度

# 多模态图片约束（Data URL 直存方案，与头像一致；SSE 请求体携带）
_IMAGE_RE = re.compile(r"^data:image/(png|jpe?g|webp);base64,[A-Za-z0-9+/=\s]+$")
MAX_IMAGE_CHARS = 4_000_000  # 单张 Data URL 字符上限（约 3MB 原图）


def validate_images(images: list[str]) -> list[str]:
    """校验随问图片：仅 png/jpeg/webp Data URL、单张 ≤4M 字符、最多 3 张。SSE 开始前调用。"""
    if not images:
        return []
    if len(images) > 3:
        raise HTTPException(status_code=422, detail="每次最多附带 3 张图片")
    for img in images:
        if not _IMAGE_RE.match(img or ""):
            raise HTTPException(status_code=422, detail="仅支持 png/jpg/webp 图片")
        if len(img) > MAX_IMAGE_CHARS:
            raise HTTPException(status_code=422, detail="单张图片过大（压缩后需小于 3MB）")
    return images


def _user_content(question: str, images: list[str]) -> str | list[dict]:
    """当前轮 user 消息体：带图时用 OpenAI 多模态 content parts，否则纯文本。"""
    if not images:
        return question
    return [
        {"type": "text", "text": question},
        *[{"type": "image_url", "image_url": {"url": img}} for img in images],
    ]


def _strip_images(messages: list[dict]) -> list[dict]:
    """把消息中的多模态 content parts 退化为纯文本（模型不支持视觉时降级用）。"""
    out: list[dict] = []
    for m in messages:
        if isinstance(m.get("content"), list):
            text = " ".join(p.get("text", "") for p in m["content"] if p.get("type") == "text")
            out = [*out, {**m, "content": f"{text}\n（用户上传了图片，当前模型不支持图片识别，请据文字回答）"}]
        else:
            out = [*out, m]
    return out

# ---------- 工具定义与提示词 ----------

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "retrieve",
            "description": "检索企业知识库文档片段。回答公司制度、流程、文档内容等问题前必须先调用。",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "检索关键词或问题改写"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "server_admin",
            "description": "只读探查服务器状态（MCP 风格）。action 可选：system_info 系统信息 / disk 磁盘占用 / process 进程列表 / network 网络连接统计 / file_list 目录浏览 / file_read 读取项目内文本文件。仅当用户询问服务器、磁盘、进程、网络或项目文件相关问题时调用；全部为只读操作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["system_info", "disk", "process", "network", "file_list", "file_read"],
                        "description": "要执行的只读探查动作",
                    },
                    "path": {"type": "string", "description": "file_list/file_read 的项目内相对路径，缺省为项目根目录"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nl2sql",
            "description": "查询产品数据表(product)，返回实时数据。回答产品库存、价格、分类、数量等数据问题前必须先调用。",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "自然语言数据问题"}},
                "required": ["question"],
            },
        },
    },
]

AGENT_SYSTEM_PROMPT = (
    "你是企业管理系统的AI助手，负责回答员工关于公司制度流程与产品数据的问题。可调用工具：\n"
    "1. retrieve：检索企业知识库（制度、流程、文档等），回答此类问题前先调用；\n"
    "2. nl2sql：查询产品数据表(product)的实时数据（库存、价格、分类等），回答产品数据问题前先调用。\n"
    "规则：每次只调用一个工具；工具结果足够时不要再调用；与制度、产品数据无关的问题直接回答，不调用工具。"
)

GENERATE_SYSTEM_PROMPT = (
    "你是企业管理系统的智能助手，用简体中文回答。规则：\n"
    "1. 若提供了知识库参考资料，回答须依据资料，并在对应句子末尾用 [1][2] 标注引用，资料中没有的内容如实说明；\n"
    "2. 若对话中包含产品数据查询结果，用清晰的表格或列表呈现数据，禁止编造数字；\n"
    "3. 回答简洁、结构化，适合企业内部沟通场景。"
)


def _generate_system(context: str) -> str:
    if not context:
        return GENERATE_SYSTEM_PROMPT
    return f"{GENERATE_SYSTEM_PROMPT}\n\n参考资料：\n{context}"


# ---------- LangGraph 状态与节点 ----------


class AgentState(TypedDict, total=False):
    messages: Annotated[list[dict], operator.add]   # OpenAI 格式消息（含本轮 tool 消息）
    context_chunks: list[dict]                       # 最近一次 retrieve 命中的切片
    citations: list[dict]                            # generate 产出的引用列表
    tool_trace: Annotated[list[dict], operator.add]  # 工具调用记录
    rounds: int                                      # 已发生工具调用轮次
    user_id: int
    username: str
    deep_thinking: bool
    images: list[str]
    server_admin_enabled: bool
    answer: str
    reasoning: str


def _agent_node(state: AgentState) -> dict:
    """工具调用决策：达到轮次上限则不再调用工具，直接进入生成。"""
    if state.get("rounds", 0) >= MAX_TOOL_ROUNDS:
        return {"messages": [{"role": "assistant", "content": ""}]}
    try:
        msg = llm_client.chat_with_tools(state["messages"], TOOLS_SPEC, max_tokens=1536, temperature=0.2)
    except HTTPException:
        if not state.get("images"):
            raise
        # 带图提问且模型不支持视觉输入时，退化纯文本重试一次
        msg = llm_client.chat_with_tools(
            _strip_images(state["messages"]), TOOLS_SPEC, max_tokens=1536, temperature=0.2
        )
    return {"messages": [msg]}


def _route_after_agent(state: AgentState) -> Literal["tools", "generate"]:
    last = state["messages"][-1]
    return "tools" if last.get("tool_calls") else "generate"


def _tools_node(state: AgentState) -> dict:
    """执行本轮全部工具调用，tool 结果消息进入 messages，供 agent 复盘与 generate 引用。"""
    writer = get_stream_writer()
    db = SessionLocal()
    tool_msgs: list[dict] = []
    trace: list[dict] = []
    try:
        last = state["messages"][-1]
        for tc in last.get("tool_calls", []):
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == "retrieve":
                query = str(args.get("query") or "").strip()
                writer({"kind": "tool", "tool": "retrieve", "query": query})
                content, chunks = _tool_retrieve(db, query)
                if chunks:
                    result = {"context_chunks": chunks}
                else:
                    result = {}
            elif name == "server_admin":
                action = str(args.get("action") or "")
                path = str(args.get("path") or "") or None
                if not state.get("server_admin_enabled"):
                    content = "当前账号没有服务器管理权限，无法执行该操作。请告知用户联系管理员开通。"
                else:
                    writer({"kind": "tool", "tool": "server_admin", "action": action, "path": path})
                    content = server_admin_service.run_action(action, {"path": path})
                result = {}
            elif name == "nl2sql":
                question = str(args.get("question") or "").strip()
                writer({"kind": "tool", "tool": "nl2sql", "question": question})
                content = _tool_nl2sql(db, state, question)
                result = {}
            else:
                content = f"未知工具：{name}"
                result = {}
            tool_msgs.append({"role": "tool", "tool_call_id": tc.get("id"), "name": name, "content": content})
            trace.append({"tool": name, "args": args})
        return {"messages": tool_msgs, "tool_trace": trace, "rounds": state.get("rounds", 0) + 1, **result}
    finally:
        db.close()


def _tool_retrieve(db: Session, query: str) -> tuple[str, list[dict]]:
    """知识库检索：返回 (tool结果文本, 命中切片)。"""
    kb_ids = list(db.scalars(select(KBKnowledgeBase.id).where(KBKnowledgeBase.status == 1)).all())
    if not kb_ids:
        return "当前没有启用的知识库，无法检索。请基于已有知识回答，并说明未检索到资料。", []
    if not query:
        return "检索词为空，请提供具体问题。", []
    results, _ = kb_rag_service.retrieve_with_crag(db, query=query, kb_ids=kb_ids, top_k=6)
    if not results:
        return "知识库中未检索到相关资料。请如实告知用户未找到依据。", []
    return f"已检索到 {len(results)} 条相关资料（文件/标题/页码/正文），已注入生成上下文。", results


def _tool_nl2sql(db: Session, state: AgentState, question: str) -> str:
    """产品数据查询：生成 SQL（含安全校验）→ 只读执行 → 落 nl2sql_record 留痕。"""
    if not question:
        return "数据问题为空，请提供具体问题。"
    sql = nl2sql_service.generate_sql(question)  # 内含 SELECT/仅product/LIMIT 校验，不合法 422
    rows, ms = nl2sql_service.execute_readonly(sql)
    payload = {"columns": list(rows[0].keys()) if rows else [], "rows": rows}
    payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    rec = NL2SQLRecord(
        user_id=state["user_id"], question=question, generated_sql=sql,
        review_status=3, result_json=json.dumps(payload, ensure_ascii=False),
        execution_ms=ms, executed_at=datetime.now(),
    )
    db.add(rec)
    db.commit()
    write_log(db, user_id=state["user_id"], username=state.get("username"), module="NL2SQL",
              action="AI助手执行SQL", params={"question": question, "rows": len(rows), "ms": ms}, result=1)
    preview = json.dumps(rows[:20], ensure_ascii=False, default=str)[:TOOL_RESULT_MAX_CHARS]
    return (f"已执行只读SQL：{sql}\n共 {len(rows)} 行，耗时 {ms} ms。"
            f"结果JSON（最多前20行）：{preview}")


def _generate_node(state: AgentState) -> dict:
    """最终回答：流式产出（custom 事件逐 delta 上报），引用随流下发。"""
    writer = get_stream_writer()
    chunks = state.get("context_chunks") or []
    context = "\n\n".join(
        f"[{i + 1}] （文件：{c.get('file_name')}，标题路径：{c.get('title_path')}，页码：{c.get('page')}）\n{c.get('content')}"
        for i, c in enumerate(chunks)
    )
    msgs = [{"role": "system", "content": _generate_system(context)}] + state["messages"]
    deep = state.get("deep_thinking", False)
    answer: list[str] = []
    reasoning: list[str] = []

    def _emit(kind: str, delta: str) -> None:
        if kind == "reasoning":
            if deep:
                reasoning.append(delta)
                writer({"kind": "reasoning", "delta": delta})
        else:
            answer.append(delta)
            writer({"kind": "message", "delta": delta})

    try:
        try:
            for kind, delta in llm_client.chat_stream(msgs, max_tokens=3072, temperature=0.3):
                _emit(kind, delta)
        except HTTPException:
            if not state.get("images"):
                raise
            # 带图提问且模型不支持视觉输入（请求即被拒，尚未产出增量）时，退化纯文本重试
            answer.clear()
            reasoning.clear()
            for kind, delta in llm_client.chat_stream(_strip_images(msgs), max_tokens=3072, temperature=0.3):
                _emit(kind, delta)
    except HTTPException as exc:
        writer({"kind": "error", "message": str(exc.detail)})
        return {"answer": "", "reasoning": "", "citations": [], "error": str(exc.detail)}
    citations = _build_citations(chunks)
    if citations:
        writer({"kind": "citations", "citations": citations})
    return {"answer": "".join(answer), "reasoning": "".join(reasoning), "citations": citations}


def _build_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "index": i + 1,
            "file_name": c.get("file_name"),
            "title_path": c.get("title_path"),
            "page": c.get("page"),
            "similarity": c.get("similarity"),
            "snippet": (c.get("content") or "")[:120] + "…",
        }
        for i, c in enumerate(chunks)
    ]


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("agent", _agent_node)
    g.add_node("tools", _tools_node)
    g.add_node("generate", _generate_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", _route_after_agent, {"tools": "tools", "generate": "generate"})
    g.add_edge("tools", "agent")
    g.add_edge("generate", END)
    return g.compile()


_GRAPH = _build_graph()


# ---------- SSE 问答 ----------


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def chat_sse(
    user_id: int, username: str, *,
    question: str, conversation_id: int | None, deep_thinking: bool,
    images: list[str] | None = None, enable_server_admin: bool = False,
):
    """SSE 生成器：建/续会话 → 运行 LangGraph 图并转发 custom 事件 → 持久化消息。"""
    db = SessionLocal()
    try:
        if conversation_id:
            conv = db.get(AIConversation, conversation_id)
            if conv is None or conv.status == 2 or conv.user_id != user_id:
                raise HTTPException(status_code=404, detail="会话不存在")
        else:
            conv = AIConversation(user_id=user_id, title=question[:32] or "新会话", status=1, source="ai")
            db.add(conv)
            db.commit()
        yield _sse("meta", {"conversation_id": conv.id})

        recent = db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id, AIMessage.role.in_(["user", "assistant"]))
            .order_by(AIMessage.id.desc())
            .limit(HISTORY_ROUNDS * 2)
        ).all()
        recent.reverse()
        history = [{"role": m.role, "content": m.content} for m in recent]

        imgs = validate_images(images or [])
        db.add(AIMessage(
            conversation_id=conv.id, role="user", content=question,
            attachments=[{"type": "image", "url": img} for img in imgs] or None,
        ))
        db.commit()

        init_state: AgentState = {
            "messages": [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                *history,
                {"role": "user", "content": _user_content(question, imgs)},
            ],
            "context_chunks": [],
            "citations": [],
            "tool_trace": [],
            "rounds": 0,
            "user_id": user_id,
            "username": username,
            "deep_thinking": deep_thinking,
            "images": imgs,
            "server_admin_enabled": enable_server_admin,
        }
        final_state: AgentState = {}
        try:
            for mode, payload in _GRAPH.stream(
                init_state, stream_mode=["custom", "values"], config={"recursion_limit": 50}
            ):
                if mode == "custom":
                    kind = payload.get("kind")
                    if kind == "reasoning":
                        yield _sse("reasoning", {"delta": payload["delta"]})
                    elif kind == "message":
                        yield _sse("message", {"conversation_id": conv.id, "delta": payload["delta"]})
                    elif kind == "tool":
                        yield _sse("tool", {k: v for k, v in payload.items() if k != "kind"})
                    elif kind == "citations":
                        yield _sse("citations", payload["citations"])
                    elif kind == "error":
                        yield _sse("error", {"message": payload["message"]})
                        return
                else:
                    final_state = payload
        except HTTPException as exc:
            yield _sse("error", {"message": str(exc.detail)})
            return
        except Exception as exc:  # 图执行异常兜底，避免连接悬挂
            yield _sse("error", {"message": f"处理失败：{exc}"})
            return

        # 先落 tool 消息再落 assistant 终答，保证时间线为：工具调用 → 最终回答
        for m in final_state.get("messages", []):
            if m.get("role") == "tool":
                db.add(AIMessage(
                    conversation_id=conv.id, role="tool", tool_name=m.get("name"),
                    content=(m.get("content") or "")[:TOOL_STORE_MAX_CHARS],
                ))
        assistant = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content=final_state.get("answer", ""),
            reasoning_content=(final_state.get("reasoning") or None) if deep_thinking else None,
            citations=final_state.get("citations") or None,
        )
        db.add(assistant)
        conv.updated_at = datetime.now()
        db.commit()
        yield _sse("done", {"conversation_id": conv.id, "message_id": assistant.id})
    except HTTPException as exc:
        yield _sse("error", {"message": str(exc.detail)})
    finally:
        db.close()


# ---------- 会话管理 ----------


def serialize_conversation(c: AIConversation) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def serialize_message(m: AIMessage) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "reasoning_content": m.reasoning_content,
        "tool_name": m.tool_name,
        "citations": m.citations,
        "attachments": m.attachments,
        "created_at": m.created_at.isoformat(),
    }


def list_conversations(db: Session, *, user_id: int, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    q = select(AIConversation).where(
        AIConversation.user_id == user_id, AIConversation.status != 2, AIConversation.source == "ai"
    )
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(AIConversation.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_conversation(c) for c in items], total


def _get_own_conversation(db: Session, conversation_id: int, user_id: int) -> AIConversation:
    conv = db.get(AIConversation, conversation_id)
    if conv is None or conv.status == 2 or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


def get_conversation(db: Session, conversation_id: int, operator: object) -> dict:
    conv = _get_own_conversation(db, conversation_id, operator.id)
    messages = db.scalars(
        select(AIMessage).where(AIMessage.conversation_id == conv.id).order_by(AIMessage.id)
    ).all()
    return {**serialize_conversation(conv), "messages": [serialize_message(m) for m in messages]}


def delete_conversation(db: Session, conversation_id: int, operator) -> None:
    conv = _get_own_conversation(db, conversation_id, operator.id)
    conv.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="AI助手",
              action="删除会话", params={"id": conv.id}, result=1)
