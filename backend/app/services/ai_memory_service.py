"""AI 助手长期记忆服务：按用户隔离的记忆提取、去重合并、向量召回与注入。

设计要点：
- 事实源在 MySQL ai_memory 表（软删/审计友好），向量与定位 id 写 Chroma 单一 collection
  ai_memory（metadata 带 user_id），检索后一律回 MySQL 按 user_id/status 二次过滤——
  用户隔离以 MySQL 层为强制边界（沿用知识库"Chroma metadata 过滤不可靠"的经验）。
- 提取在每轮问答结束后由路由层 BackgroundTask 异步执行（读库取最后一轮 user/assistant），
  失败静默降级，绝不影响问答主流程。
- 解析/校验/去重/token 估算均为纯函数，可脱离 LLM 与数据库单测。
"""
import json
import logging
import math
import re
import threading
from datetime import datetime

import chromadb
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ai import AIMemory, AIMessage
from app.services import kb_rag_service, llm_client, vector_store
from app.services.operation_log_service import write_log

logger = logging.getLogger(__name__)

# ---------- 常量 ----------

COLLECTION_NAME = "ai_memory"
MEMORY_LIMIT = 100          # 每用户记忆条数上限，超出软删最旧
RECALL_TOP_K = 5            # 提问时召回条数
RECALL_MIN_SIM = 0.30       # 召回相似度阈值，低于丢弃
DEDUP_SIM = 0.90            # 视为重复/矛盾的相似度下限（更新合并而非新增）
MAX_MEMORY_CHARS = 300      # 单条记忆字符上限（与表列宽一致）
MAX_EXTRACT_CHARS = 2000    # 参与提取的对话文本上限
INJECT_MAX_CHARS = 1500     # 注入 system prompt 的记忆文本总上限
RECENCY_DECAY = 0.01        # 召回排序的时效衰减：每过一天相似度减 0.01

# 偏好键（sys_user.preferences JSON 白名单之一，由 profile_service 注册）
ENABLED_KEY = "ai_memory_enabled"

# 敏感信息兜底过滤：手机号 / 身份证号 / 常见密钥格式（提取 prompt 已约束，此为第二道防线）
_SENSITIVE_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),                    # 手机号
    re.compile(r"\d{17}[\dXx]"),                   # 身份证号
    re.compile(r"sk-[A-Za-z0-9]{12,}"),            # OpenAI 风格密钥（不设词边界：前置中文字符时 \b 不生效）
    re.compile(r"(?i)(api[_-]?key|secret|token|密码)\s*[:=＝]\s*\S+"),  # 键值型密钥
]

_EXTRACT_PROMPT = (
    "从下面的用户与AI助手对话中，提取值得长期记住的【用户个人事实或偏好】。\n"
    "规则：\n"
    "1. 只提取关于用户本人的稳定信息：身份/部门/职责、长期偏好、重要的工作上下文；\n"
    "2. 不提取：一次性任务、闲聊寒暄、知识库问答内容本身、产品数据查询结果；\n"
    "3. 严禁记录密码、密钥、证件号、手机号等敏感信息；\n"
    "4. 若对话中用户修正了旧偏好，输出修正后的最新表述；\n"
    "5. 每条不超过100字；没有值得记录的内容时返回空数组。\n"
    '仅输出 JSON 数组，格式：[{"type":"fact或preference","content":"记忆内容"}]'
)

# ---------- Chroma collection ----------

_collection_cache: dict = {}


def _get_collection():
    """记忆向量集合：单 collection，维度取默认向量模型探针（创建时锁定）。"""
    if "col" in _collection_cache:
        return _collection_cache["col"]
    col = vector_store.get_or_create_collection(COLLECTION_NAME, _memory_dimension())
    _collection_cache["col"] = col
    return col


def _memory_dimension() -> int:
    try:
        return kb_rag_service.probe_embedding_dimension()
    except Exception:
        return 1024


def _memory_dim_of(col) -> int:
    return int((col.metadata or {}).get("dimension") or 1024)


# ---------- 纯函数（可单测） ----------


def estimate_tokens(text: str) -> int:
    """启发式 token 估算：CJK 字符约 1 字/token，其余约 4 字符/token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + math.ceil((len(text) - cjk) / 4)


def sanitize_memory(content: str) -> str | None:
    """记忆清洗：敏感信息兜底过滤 + 去空白 + 长度裁剪；无效返回 None。"""
    text = (content or "").strip()
    if not text:
        return None
    for pat in _SENSITIVE_PATTERNS:
        if pat.search(text):
            return None
    return text[:MAX_MEMORY_CHARS]


def parse_extraction(raw: str) -> list[dict]:
    """解析提取模型输出为 [{type, content}]：容错处理代码块围栏/前后杂文/非法项。

    防御性校验：type 归一化（非 fact/preference 落 fact），内容过长截断，含敏感信息丢弃。
    """
    if not raw:
        return []
    m = re.search(r"\[.*\]", raw, re.S)  # 截取首个 JSON 数组，容忍模型前后赘述
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for item in items[:10]:
        if not isinstance(item, dict):
            continue
        content = sanitize_memory(str(item.get("content") or ""))
        if not content:
            continue  # 含敏感信息/空内容直接丢弃
        mtype = str(item.get("type") or "fact")
        out.append({"type": mtype if mtype in ("fact", "preference") else "fact", "content": content})
    return out


def merge_decision(
    new_content: str, existing: list[dict], *, dedup_sim: float = DEDUP_SIM
) -> tuple[str, int | None]:
    """新记忆 vs 既有记忆的合并决策（纯函数）。

    existing: [{id, content, similarity}]（已按该用户检索并过滤）
    返回 (action, target_id)：action ∈ new（全新增）/ update（合并更新）/ skip（完全重复）。
    """
    new_key = new_content.strip().lower()
    best: dict | None = None
    for e in existing:
        if e["content"].strip().lower() == new_key:
            return "skip", e["id"]
        if best is None or (e.get("similarity") or 0) > (best.get("similarity") or 0):
            best = e
    if best and (best.get("similarity") or 0) >= dedup_sim:
        # 语义高度相似：视为同一事项的补充/修正 → 更新旧记忆（内容以新为准）
        return "update", best["id"]
    return "new", None


def format_injection(memories: list[dict], *, max_chars: int = INJECT_MAX_CHARS) -> str:
    """把召回记忆格式化为 system prompt 附加段（带字符预算，防止 prompt 膨胀）。"""
    if not memories:
        return ""
    body = ""
    for m in memories:
        line = f"- {m['content']}\n"
        if len(body) + len(line) > max_chars:
            break
        body += line
    if not body:
        return ""
    return (
        "\n\n以下是关于当前用户的长期记忆（历史对话中了解到的信息，供个性化参考；"
        "与当前问题无关时忽略）：\n" + body.rstrip()
    )


# ---------- 向量读写 ----------


def _embed_memory(texts: list[str], db: Session | None = None) -> list[list[float]]:
    col = _get_collection()
    return kb_rag_service.embed_texts(texts, _memory_dim_of(col), db=db)


def _store_vectors(db: Session, memories: list[AIMemory]) -> None:
    """记忆向量写入 Chroma（覆盖同 ID）。"""
    col = _get_collection()
    vectors = _embed_memory([m.content for m in memories], db=db)
    vector_store.upsert_points(
        col,
        ids=[f"m{m.id}" for m in memories],
        vectors=vectors,
        documents=[m.content for m in memories],
        metadatas=[
            {"user_id": m.user_id, "memory_id": m.id, "memory_type": m.memory_type, "status": str(m.status)}
            for m in memories
        ],
    )


def _remove_vector(memory_id: int) -> None:
    vector_store.delete_ids(_get_collection(), [f"m{memory_id}"])


# ---------- 偏好开关 ----------


def memory_enabled(db: Session, user_id: int) -> bool:
    """读取用户偏好 ai_memory_enabled（默认开启；读取失败按开启处理，召回方再兜底）。"""
    try:
        from app.models.user import SysUser

        user = db.get(SysUser, user_id)
        prefs = user.preferences or {} if user is not None else {}
        return bool(prefs.get(ENABLED_KEY, True))
    except Exception:
        return True


# ---------- 提取入库（后台任务入口） ----------


def extract_and_store(db: Session, user_id: int, conversation_id: int) -> int:
    """读取最后一轮 user/assistant → LLM 提取 → 去重入库。返回新增/更新条数。"""
    last = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id, AIMessage.role.in_(["user", "assistant"]))
            .order_by(AIMessage.id.desc())
            .limit(2)
        ).all()
    )
    last.reverse()
    if len(last) < 2 or last[0].role != "user" or last[1].role != "assistant":
        return 0
    dialogue = f"用户：{last[0].content[:MAX_EXTRACT_CHARS]}\n助手：{last[1].content[:MAX_EXTRACT_CHARS]}"
    raw = llm_client.chat_once(
        [
            {"role": "system", "content": _EXTRACT_PROMPT},
            {"role": "user", "content": dialogue},
        ],
        max_tokens=512,
        temperature=0,
    )
    items = parse_extraction(raw)
    if not items:
        return 0
    return save_memories(db, user_id, items, conversation_id)


def _maybe_generate_title(db: Session, conversation_id: int) -> None:
    """首轮问答后自动生成会话标题（默认标题=问题前32字符时才覆盖）。"""
    from app.models.ai import AIConversation

    conv = db.get(AIConversation, conversation_id)
    if conv is None or conv.status == 2:
        return
    first_user = db.scalars(
        select(AIMessage)
        .where(AIMessage.conversation_id == conv.id, AIMessage.role == "user")
        .order_by(AIMessage.id.asc())
        .limit(1)
    ).first()
    if first_user is None or (conv.title or "") != (first_user.content or "")[:32]:
        return  # 已有自定义标题或非首轮
    raw = llm_client.chat_once(
        [
            {"role": "system", "content": "为下面的对话生成一个不超过12字的中文标题，概括主题。直接输出标题本身，不要任何其他内容。"},
            {"role": "user", "content": (first_user.content or "")[:300]},
        ],
        max_tokens=32,
        temperature=0.3,
    )
    title = sanitize_memory(raw.strip().strip('"「」')) or ""
    if title:
        conv.title = title[:64]
        db.commit()


def finalize_round(holder: dict, user_id: int, username: str) -> None:
    """每轮问答结束后异步执行（BackgroundTask）：记忆提取入库 + 会话标题自动总结。

    holder 由 chat_sse 填写（ok/conversation_id）；任何异常仅记日志，不外抛。
    """
    if not holder.get("ok"):
        return
    conversation_id = holder.get("conversation_id")
    if not conversation_id:
        return
    db = SessionLocal()
    try:
        saved = 0
        if memory_enabled(db, user_id):
            try:
                saved = extract_and_store(db, user_id, conversation_id)
            except Exception:
                logger.warning("ai_memory 提取失败 user_id=%s conv=%s", user_id, conversation_id, exc_info=True)
        try:
            _maybe_generate_title(db, conversation_id)
        except Exception:
            logger.warning("会话标题生成失败 conv=%s", conversation_id, exc_info=True)
        if saved:
            write_log(db, user_id=user_id, username=username, module="AI助手",
                      action="记忆提取", params={"conversation_id": conversation_id, "count": saved}, result=1)
            logger.info("ai_memory 提取入库 user_id=%s conv=%s 条数=%s", user_id, conversation_id, saved)
    finally:
        db.close()


_user_memory_locks: dict[int, threading.Lock] = {}
_user_locks_guard = threading.Lock()


def _user_memory_lock(user_id: int) -> threading.Lock:
    """同一用户的记忆写入按 user_id 串行化，避免两个后台提取任务并发去重/插入。"""
    with _user_locks_guard:
        return _user_memory_locks.setdefault(user_id, threading.Lock())


def save_memories(
    db: Session, user_id: int, items: list[dict], conversation_id: int | None
) -> int:
    """批量入库：逐条敏感过滤 → 相似去重（skip/update/new）→ 上限淘汰。返回实际新增/更新条数。

    并发：同一用户的提取任务按 user_id 进程内锁串行化。
    事务：先 flush 占位拿 id → 向量写成功后统一提交；向量写失败整体回滚，
    避免「MySQL 有行但 Chroma 无向量、该记忆永不召回」的双写不一致。
    审计由调用方 finalize_round 汇总写一条日志（避免高频写放大）。
    """
    with _user_memory_lock(user_id):
        saved = 0
        try:
            for item in items:
                content = sanitize_memory(item.get("content") or "")
                if not content:
                    continue
                existing = _search_existing(db, user_id, content)
                action, target_id = merge_decision(content, existing)
                if action == "skip":
                    continue
                if action == "update" and target_id:
                    mem = db.get(AIMemory, target_id)
                    if mem is not None and mem.user_id == user_id and mem.status == 1:
                        mem.content = content
                        mem.memory_type = item.get("type") or mem.memory_type
                        mem.source_conversation_id = conversation_id
                        db.flush()
                        _store_vectors(db, [mem])
                        saved += 1
                    continue
                mem = AIMemory(
                    user_id=user_id, content=content, memory_type=item.get("type") or "fact",
                    source_conversation_id=conversation_id,
                )
                db.add(mem)
                db.flush()
                _store_vectors(db, [mem])
                saved += 1
                _enforce_limit(db, user_id)
            db.commit()
            return saved
        except Exception:
            db.rollback()
            raise


def _search_existing(db: Session, user_id: int, query: str) -> list[dict]:
    """检索该用户既有记忆（MySQL 强制 user_id/status 过滤），供去重决策。"""
    col = _get_collection()
    try:
        qv = kb_rag_service.embed_texts([query], _memory_dim_of(col), db=db)[0]
        res = vector_store.query(col, qv, 10)
    except Exception:
        logger.warning("ai_memory 去重检索失败", exc_info=True)
        return []
    ids = [int(str(mid).lstrip("m")) for mid in res["ids"][0]]
    if not ids:
        return []
    rows = db.scalars(
        select(AIMemory).where(AIMemory.id.in_(ids), AIMemory.user_id == user_id, AIMemory.status == 1)
    ).all()
    by_id = {m.id: m for m in rows}
    out: list[dict] = []
    for mid, doc, dist in zip(res["ids"][0], res["documents"][0], res["distances"][0]):
        row = by_id.get(int(str(mid).lstrip("m")))
        if row is None:
            continue  # MySQL 侧二次过滤：软删/他人记忆不可见
        out.append({"id": row.id, "content": doc or row.content, "similarity": round(max(0.0, 1.0 - dist), 4)})
    return out


def _enforce_limit(db: Session, user_id: int) -> None:
    """每用户记忆条数上限：超出软删最旧（向量同步移除）。"""
    rows = db.scalars(
        select(AIMemory).where(AIMemory.user_id == user_id, AIMemory.status == 1)
        .order_by(AIMemory.updated_at.asc(), AIMemory.id.asc())
    ).all()
    overflow = rows[: max(0, len(rows) - MEMORY_LIMIT)]
    for mem in overflow:
        mem.status = 2
        _remove_vector(mem.id)
    if overflow:
        db.commit()


# ---------- 记忆管理（查看 / 编辑 / 删除 / 清空） ----------


def list_memories(db: Session, user_id: int, *, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    """本人记忆分页列表（仅 status=1，按更新时间倒序）。"""
    from sqlalchemy import func as _func

    q = select(AIMemory).where(AIMemory.user_id == user_id, AIMemory.status == 1)
    total = db.scalar(select(_func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(AIMemory.updated_at.desc(), AIMemory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": m.id, "content": m.content, "memory_type": m.memory_type,
            "source_conversation_id": m.source_conversation_id,
            "created_at": m.created_at.isoformat(), "updated_at": m.updated_at.isoformat(),
        }
        for m in rows
    ]
    return items, total


def edit_memory(db: Session, memory_id: int, operator, content: str) -> dict:
    """编辑本人记忆内容（重新向量化）。非本人/已删除一律 404。"""
    mem = db.get(AIMemory, memory_id)
    if mem is None or mem.status == 2 or mem.user_id != operator.id:
        raise HTTPException(status_code=404, detail="记忆不存在")
    new_content = sanitize_memory(content)
    if not new_content:
        raise HTTPException(status_code=422, detail="记忆内容包含敏感信息或不合法")
    mem.content = new_content
    db.commit()
    _store_vectors(db, [mem])
    write_log(db, user_id=operator.id, username=operator.username, module="AI助手",
              action="编辑记忆", params={"memory_id": mem.id, "content": new_content[:50]}, result=1)
    return {"id": mem.id, "content": mem.content, "memory_type": mem.memory_type}


def delete_memory(db: Session, memory_id: int, operator) -> None:
    """删除本人单条记忆（软删除并移除向量）。"""
    mem = db.get(AIMemory, memory_id)
    if mem is None or mem.status == 2 or mem.user_id != operator.id:
        raise HTTPException(status_code=404, detail="记忆不存在")
    mem.status = 2
    db.commit()
    _remove_vector(mem.id)
    write_log(db, user_id=operator.id, username=operator.username, module="AI助手",
              action="删除记忆", params={"memory_id": mem.id}, result=1)


def clear_memories(db: Session, operator) -> int:
    """清空本人全部记忆（软删除并移除向量）。返回清除条数。"""
    rows = db.scalars(
        select(AIMemory).where(AIMemory.user_id == operator.id, AIMemory.status == 1)
    ).all()
    for mem in rows:
        mem.status = 2
        _remove_vector(mem.id)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="AI助手",
              action="清空记忆", params={"count": len(rows)}, result=1)
    return len(rows)


# ---------- 召回注入（提问时） ----------


def recall(db: Session, user_id: int, query: str) -> list[dict]:
    """按当前问题召回该用户相关记忆：阈值 + 时效衰减排序 + 字符预算。

    返回 [{id, content, memory_type, similarity}]；异常/未配置向量模型时返回空列表。
    """
    if not query.strip():
        return []
    col = _get_collection()
    try:
        qv = kb_rag_service.embed_texts([query], _memory_dim_of(col), db=db)[0]
        res = vector_store.query(col, qv, RECALL_TOP_K * 4)
    except Exception:
        logger.warning("ai_memory 召回检索失败", exc_info=True)
        return []
    ids = [int(str(mid).lstrip("m")) for mid in res["ids"][0]]
    if not ids:
        return []
    rows = db.scalars(
        select(AIMemory).where(AIMemory.id.in_(ids), AIMemory.user_id == user_id, AIMemory.status == 1)
    ).all()
    by_id = {m.id: m for m in rows}
    candidates: list[dict] = []
    now = datetime.now()
    for mid, doc, dist in zip(res["ids"][0], res["documents"][0], res["distances"][0]):
        row = by_id.get(int(str(mid).lstrip("m")))
        if row is None:
            continue  # MySQL 侧二次过滤（隔离边界）
        sim = max(0.0, 1.0 - dist)
        days = max(0.0, (now - row.updated_at).total_seconds() / 86400)
        candidates.append({
            "id": row.id, "content": doc or row.content, "memory_type": row.memory_type,
            "similarity": round(sim, 4), "score": sim - RECENCY_DECAY * days,
        })
    candidates = [c for c in candidates if c["similarity"] >= RECALL_MIN_SIM]
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return [
        {"id": c["id"], "content": c["content"], "memory_type": c["memory_type"], "similarity": c["similarity"]}
        for c in candidates[:RECALL_TOP_K]
    ]

