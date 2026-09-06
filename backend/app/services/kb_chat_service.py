"""知识库问答服务（M3-T3）：检索调试、多轮改写、SSE 流式问答与会话持久化。"""
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.models.kb import KBKnowledgeBase
from app.models.user import SysUser
from app.db.session import SessionLocal
from app.services import kb_rag_service
from app.services.kb_rag_service import retrieve_with_crag
from app.services.llm_client import chat_once, chat_stream
from app.services.operation_log_service import write_log

TOP_K_DEFAULT = 6
HISTORY_ROUNDS = 3  # 多轮改写取最近三轮对话

SYSTEM_PROMPT = (
    "你是企业知识库助手。请仅根据参考资料回答用户问题，"
    "如果资料中没有相关内容，请明确回答\"知识库中没有相关资料\"，不要编造。"
    "回答使用简体中文，简洁准确，并在引用资料处用 [1][2] 标注编号。"
)

REWRITE_PROMPT = (
    "请根据对话历史，把用户最新问题改写为一个不依赖上下文、可以独立用于知识库检索的完整查询。"
    "只输出改写后的查询本身，不要任何解释或引号。如果最新问题已经完整独立，原样输出。\n\n对话历史：\n{history}\n用户：{question}\n改写后的查询："
)


def validate_kbs(db: Session, kb_ids: list[int]) -> list[KBKnowledgeBase]:
    if not kb_ids:
        raise HTTPException(status_code=422, detail="请选择至少一个知识库")
    kbs = db.scalars(
        select(KBKnowledgeBase).where(KBKnowledgeBase.id.in_(kb_ids), KBKnowledgeBase.status != 2)
    ).all()
    if len(kbs) != len(set(kb_ids)):
        raise HTTPException(status_code=422, detail="存在无效的知识库")
    return kbs


def search_debug(db: Session, user: SysUser, *, query: str, kb_ids: list[int], top_k: int) -> list[dict]:
    """检索调试：返回切片、相似度分数与溯源信息。"""
    validate_kbs(db, kb_ids)
    results = retrieve(db, query=query, kb_ids=kb_ids, top_k=top_k)
    write_log(db, user_id=user.id, username=user.username, module="知识库",
              action="检索调试", params={"query": query, "kb_ids": kb_ids, "top_k": top_k,
                                         "hits": len(results)}, result=1)
    return results


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _rewrite_query(question: str, history: list[AIMessage]) -> str:
    """多轮改写：结合最近对话历史生成独立检索词；失败或为空时回退原问题。"""
    if not history:
        return question
    lines = [f"{'用户' if m.role == 'user' else '助手'}：{m.content[:200]}" for m in history]
    try:
        rewritten = chat_once([
            {"role": "user", "content": REWRITE_PROMPT.format(history="\n".join(lines), question=question)}
        ])
    except HTTPException:
        return question
    rewritten = rewritten.strip().strip('"“”')
    if not rewritten or len(rewritten) > 120 or rewritten.startswith(("抱歉", "作为")):
        return question
    return rewritten


def _build_citations(results: list[dict]) -> list[dict]:
    return [
        {
            "index": i + 1,
            "file_name": r.get("file_name"),
            "title_path": r.get("title_path"),
            "page": r.get("page"),
            "similarity": r.get("similarity"),
            "snippet": (r["content"][:120] + "…") if len(r["content"]) > 120 else r["content"],
        }
        for i, r in enumerate(results)
    ]


def _build_context(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results, start=1):
        source = f"文件：{r.get('file_name') or '未知'}"
        if r.get("title_path"):
            source += f"，标题路径：{r['title_path']}"
        if r.get("page"):
            source += f"，页码：{r['page']}"
        parts.append(f"[{i}] （{source}）\n{r['content']}")
    return "\n\n".join(parts)


def chat_sse(user_id: int, username: str, *, question: str, kb_ids: list[int],
             conversation_id: int | None, top_k: int):
    """SSE 问答生成器：message/reasoning 增量 → citations → done；独立数据库会话。

    事件序列：message* → [reasoning*]（推理模型） → citations → done；异常产出 error 事件。
    """
    db = SessionLocal()
    try:
        kbs = validate_kbs(db, kb_ids)
        _ = kbs

        # 1. 会话：续聊校验归属，新会话以首问为标题
        if conversation_id is not None:
            conv = db.get(AIConversation, conversation_id)
            if conv is None or conv.user_id != user_id:
                raise HTTPException(status_code=404, detail="会话不存在")
        else:
            conv = AIConversation(user_id=user_id, title=question[:32], source="kb")
            db.add(conv)
            db.flush()

        # 2. 最近三轮历史 → 多轮改写 → 检索
        history = db.scalars(
            select(AIMessage).where(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.id.desc()).limit(HISTORY_ROUNDS * 2)
        ).all()[::-1]
        search_query = _rewrite_query(question, history)
        results, used_query = retrieve_with_crag(db, query=search_query, kb_ids=kb_ids, top_k=top_k)
        if used_query != search_query:
            search_query = used_query  # CRAG 校正后实际生效的检索词
        citations = _build_citations(results)

        # 3. 持久化用户消息
        db.add(AIMessage(conversation_id=conv.id, role="user", content=question))
        conv.updated_at = datetime.now()
        db.commit()

        yield _sse("meta", {"conversation_id": conv.id, "search_query": search_query})

        # 4. 组装上下文流式生成
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in history:
            messages.append({"role": "user" if m.role == "user" else "assistant", "content": m.content})
        messages.append({
            "role": "user",
            "content": f"参考资料：\n{_build_context(results) if results else '（无）'}\n\n用户问题：{question}",
        })

        answer_parts: list[str] = []
        try:
            for kind, delta in chat_stream(messages):
                if kind == "content":
                    answer_parts.append(delta)
                    yield _sse("message", {"conversation_id": conv.id, "delta": delta})
                else:
                    yield _sse("reasoning", {"delta": delta})
        except HTTPException as exc:
            if not answer_parts:
                yield _sse("error", {"message": exc.detail})
                return
            yield _sse("error", {"message": f"生成中断：{exc.detail}"})

        answer = "".join(answer_parts)

        # 5. 持久化助手消息并下发引用与结束事件
        msg = AIMessage(conversation_id=conv.id, role="assistant", content=answer, citations=citations)
        db.add(msg)
        conv.updated_at = datetime.now()
        db.commit()

        yield _sse("citations", citations)
        yield _sse("done", {"conversation_id": conv.id, "message_id": msg.id,
                            "references_used": len(citations)})

        write_log(db, user_id=user_id, username=username, module="知识库",
                  action="知识库问答", params={"conversation_id": conv.id, "question": question[:100],
                                               "kb_ids": kb_ids, "hits": len(citations)}, result=1)
    except HTTPException as exc:
        yield _sse("error", {"message": exc.detail})
    except Exception as exc:  # noqa: BLE001  流内异常必须作为事件下发
        yield _sse("error", {"message": f"服务器内部错误：{exc}"})
    finally:
        db.close()


def list_conversations(db: Session, user: SysUser, *, page: int = 1, page_size: int = 20):
    q = select(AIConversation).where(
        AIConversation.user_id == user.id, AIConversation.source != "ai"  # 排除 AI助手会话
    )
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    convs = db.scalars(q.order_by(AIConversation.updated_at.desc())
                       .offset((page - 1) * page_size).limit(page_size)).all()
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat(),
         "updated_at": c.updated_at.isoformat()}
        for c in convs
    ], total


def conversation_detail(db: Session, user: SysUser, conversation_id: int) -> dict:
    conv = db.get(AIConversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = db.scalars(
        select(AIMessage).where(AIMessage.conversation_id == conv.id).order_by(AIMessage.id)
    ).all()
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "messages": [
            {
                "id": m.id, "role": m.role, "content": m.content,
                "citations": m.citations or [],
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }
