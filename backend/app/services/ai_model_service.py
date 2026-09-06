"""模型配置服务（M4-T1）：CRUD、同类型唯一默认、连通性测试与配置解析。

解析器约定：ai_model 中启用的默认配置优先，无则回退 .env（M0~M3 的旧方式），
保证清空模型配置后知识库问答等既有功能不受影响。
"""
import time

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ai import AIModel
from app.schemas.ai_model import AIModelCreate, AIModelUpdate
from app.services.operation_log_service import write_log
from app.utils.crypto import decrypt_api_key, encrypt_api_key, mask_api_key

# 各提供方缺省 API 地址（base_url 留空时使用）
DEFAULT_BASE_URL = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

TYPE_LABELS = {"llm": "生成模型", "embedding": "向量模型", "rerank": "重排模型"}
PROVIDER_LABELS = {
    "zhipu": "智谱",
    "dashscope": "通义百炼",
    "openai_compatible": "OpenAI兼容",
    "local": "本地部署",
}
STATUS_LABELS = {1: "启用", 0: "停用", 2: "软删除"}


def serialize_model(m: AIModel) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "model_type": m.model_type,
        "model_type_label": TYPE_LABELS.get(m.model_type, m.model_type),
        "provider": m.provider,
        "provider_label": PROVIDER_LABELS.get(m.provider, m.provider),
        "base_url": m.base_url,
        "api_key_masked": mask_api_key(m.api_key),
        "model_name": m.model_name,
        "temperature": float(m.temperature) if m.temperature is not None else None,
        "remark": m.remark,
        "is_default": bool(m.is_default),
        "status": m.status,
        "status_label": STATUS_LABELS.get(m.status, ""),
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _base_of(m: AIModel) -> str:
    """实际请求的 API 根地址：配置优先，其次提供方缺省。"""
    base = (m.base_url or "").strip().rstrip("/") or DEFAULT_BASE_URL.get(m.provider, "")
    if not base:
        raise HTTPException(status_code=422, detail="该提供方需填写接口地址（base_url）")
    return base


def list_models(db: Session, *, model_type: str | None = None, keyword: str | None = None,
                page: int = 1, page_size: int = 20):
    q = select(AIModel).where(AIModel.status != 2)
    if model_type:
        q = q.where(AIModel.model_type == model_type)
    if keyword:
        q = q.where(AIModel.name.like(f"%{keyword}%"))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    models = db.scalars(
        q.order_by(AIModel.model_type, AIModel.is_default.desc(), AIModel.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_model(m) for m in models], total


def get_model(db: Session, model_id: int) -> AIModel:
    m = db.get(AIModel, model_id)
    if m is None or m.status == 2:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return m


def _clear_default(db: Session, model_type: str, keep_id: int | None = None) -> None:
    q = select(AIModel).where(AIModel.model_type == model_type, AIModel.is_default == 1)
    if keep_id:
        q = q.where(AIModel.id != keep_id)
    for m in db.scalars(q).all():
        m.is_default = 0


def create_model(db: Session, data: AIModelCreate, operator) -> dict:
    if data.status not in (0, 1):
        raise HTTPException(status_code=422, detail="status 仅支持 1启用/0停用")
    m = AIModel(
        name=data.name, model_type=data.model_type, provider=data.provider,
        base_url=data.base_url, api_key=encrypt_api_key(data.api_key),
        model_name=data.model_name, temperature=data.temperature, remark=data.remark,
        is_default=0, status=data.status,
    )
    db.add(m)
    db.flush()
    if data.is_default:
        _clear_default(db, data.model_type, keep_id=m.id)
        m.is_default = 1
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="模型配置",
              action="新增模型", params={"id": m.id, "name": m.name, "model_type": m.model_type}, result=1)
    return serialize_model(m)


def update_model(db: Session, model_id: int, data: AIModelUpdate, operator) -> dict:
    m = get_model(db, model_id)
    updates = data.model_dump(exclude_unset=True)
    key_plain = updates.pop("api_key", None)
    if key_plain:  # 留空/None 保持原密钥
        m.api_key = encrypt_api_key(key_plain)
    if "status" in updates and updates["status"] not in (0, 1):
        raise HTTPException(status_code=422, detail="status 仅支持 1启用/0停用")
    for field, value in updates.items():
        setattr(m, field, value)
    db.flush()
    if m.is_default == 1:
        _clear_default(db, m.model_type, keep_id=m.id)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="模型配置",
              action="编辑模型", params={"id": model_id, **{k: v for k, v in updates.items() if k != "api_key"}}, result=1)
    return serialize_model(m)


def delete_model(db: Session, model_id: int, operator) -> None:
    m = get_model(db, model_id)
    m.status = 2
    m.is_default = 0
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="模型配置",
              action="删除模型", params={"id": model_id, "name": m.name}, result=1)


def set_default(db: Session, model_id: int, operator) -> dict:
    m = get_model(db, model_id)
    if m.status != 1:
        raise HTTPException(status_code=422, detail="仅启用中的模型可设为默认")
    _clear_default(db, m.model_type, keep_id=m.id)
    m.is_default = 1
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="模型配置",
              action="设为默认", params={"id": model_id, "model_type": m.model_type}, result=1)
    return serialize_model(m)


def test_model(db: Session, model_id: int, operator) -> dict:
    """连通性测试：llm 发最小对话、embedding 发维度探针；返回耗时与结果摘要。"""
    m = get_model(db, model_id)
    base = _base_of(m)
    headers = {"Authorization": f"Bearer {decrypt_api_key(m.api_key)}"}
    started = time.perf_counter()
    try:
        if m.model_type == "llm":
            with httpx.Client(timeout=30) as client:
                r = client.post(
                    f"{base}/chat/completions",
                    headers=headers,
                    json={"model": m.model_name, "messages": [{"role": "user", "content": "回复ok"}],
                          "max_tokens": 8, "temperature": 0},
                )
                if r.status_code != 200:
                    raise HTTPException(status_code=422, detail=f"调用失败：{r.text[:200]}")
                msg = r.json()["choices"][0]["message"]
                reply = (msg.get("content") or "").strip()
                reasoning = (msg.get("reasoning_content") or "").strip()
            if not reply and reasoning:
                detail = f"推理模型连通正常（思考片段：{reasoning[:30]}…）"
            else:
                detail = f"回复：{reply[:50] or '（空）'}"
        elif m.model_type == "embedding":
            with httpx.Client(timeout=30) as client:
                r = client.post(
                    f"{base}/embeddings",
                    headers=headers,
                    json={"model": m.model_name, "input": ["连通性探针"], "dimensions": 1024},
                )
                if r.status_code != 200:
                    raise HTTPException(status_code=422, detail=f"调用失败：{r.text[:200]}")
                dim = len(r.json()["data"][0]["embedding"])
            detail = f"向量维度：{dim}"
        else:
            raise HTTPException(status_code=422, detail="rerank 连通性测试将在二期接入")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 网络异常统一转为业务提示
        raise HTTPException(status_code=422, detail=f"连接异常：{exc}") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    write_log(db, user_id=operator.id, username=operator.username, module="模型配置",
              action="连通性测试", params={"id": model_id, "name": m.name}, result=1)
    return {"latency_ms": latency_ms, "detail": detail}


# ---------- 配置解析（供 llm_client / embedding 调用） ----------

def _config_of(m: AIModel) -> dict:
    return {
        "base_url": _base_of(m),
        "api_key": decrypt_api_key(m.api_key),
        "model_name": m.model_name,
        "temperature": float(m.temperature) if m.temperature is not None else None,
        "source": "db",
    }


def _enabled_default(db: Session, model_type: str) -> AIModel | None:
    return db.scalar(
        select(AIModel).where(AIModel.model_type == model_type, AIModel.is_default == 1, AIModel.status == 1)
    )


def get_default_config(model_type: str) -> dict | None:
    """指定类型的启用默认配置（自带会话，供无 db 的客户端模块调用）。"""
    db = SessionLocal()
    try:
        m = _enabled_default(db, model_type)
        return _config_of(m) if m else None
    finally:
        db.close()


def resolve_rerank_config(db: Session | None = None, model_name: str | None = None) -> dict | None:
    """重排模型配置（RAG 二期）：类型默认 → 按模型名匹配；未配置返回 None（检索跳过重排）。

    端点约定 OpenAI 生态常见的 /rerank（Cohere/Jina 风格）：POST {model, query, documents}。
    """
    owned = db is None
    db = db or SessionLocal()
    try:
        m: AIModel | None = None
        if model_name:
            m = db.scalar(
                select(AIModel).where(AIModel.model_type == "rerank", AIModel.model_name == model_name,
                                      AIModel.status == 1)
            )
        if m is None:
            m = _enabled_default(db, "rerank")
        return _config_of(m) if m else None
    finally:
        if owned:
            db.close()


def resolve_llm_config() -> dict:
    """生成模型配置：DB 默认优先，回退 .env（MIMO_*）。"""
    cfg = get_default_config("llm")
    if cfg:
        return cfg
    if not settings.MIMO_BASE_URL or not settings.MIMO_API_KEY:
        raise HTTPException(status_code=422, detail="未配置生成模型：请在模型配置页新增并设为默认，或在 .env 配置 MIMO_*")
    return {
        "base_url": settings.MIMO_BASE_URL.rstrip("/"),
        "api_key": settings.MIMO_API_KEY,
        "model_name": settings.MIMO_MODEL,
        "temperature": None,
        "source": "env",
    }


def resolve_embedding_config(db: Session | None = None, model_name: str | None = None) -> dict:
    """向量模型配置：按知识库记录的模型名匹配 → 类型默认 → .env（智谱 embedding-3）。

    传入 db 时复用调用方会话（入库/检索链路），否则自带短会话。
    """
    owned = db is None
    db = db or SessionLocal()
    try:
        m: AIModel | None = None
        if model_name:
            m = db.scalar(
                select(AIModel).where(AIModel.model_type == "embedding", AIModel.model_name == model_name,
                                      AIModel.status == 1)
            )
        if m is None:
            m = _enabled_default(db, "embedding")
        if m:
            return _config_of(m)
    finally:
        if owned:
            db.close()
    if not settings.ZHIPU_API_KEY:
        raise HTTPException(status_code=422, detail="未配置向量模型：请在模型配置页新增并设为默认，或在 .env 配置 ZHIPU_API_KEY")
    return {
        "base_url": DEFAULT_BASE_URL["zhipu"],
        "api_key": settings.ZHIPU_API_KEY,
        "model_name": "embedding-3",
        "temperature": None,
        "source": "env",
    }
