"""AI助手路由（M4-T3）：SSE 流式问答、会话列表/详情/软删。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.ai import AIChatIn
from app.services import ai_chat_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/ai", tags=["AI助手"])


@router.post("/chat")
def chat(
    data: AIChatIn,
    operator: SysUser = Depends(require_permissions("ai:chat")),
):
    """AI助手流式问答（LangGraph Agent：agent⇄tools[retrieve/nl2sql]→generate），支持图片多模态。"""
    return StreamingResponse(
        ai_chat_service.chat_sse(
            operator.id, operator.username, question=data.question.strip(),
            conversation_id=data.conversation_id, deep_thinking=data.deep_thinking,
            images=data.images,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    operator: SysUser = Depends(require_permissions("ai:chat")),
    db: Session = Depends(get_db),
):
    """我的会话分页列表（排除软删）。"""
    items, total = ai_chat_service.list_conversations(db, user_id=operator.id, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    operator: SysUser = Depends(require_permissions("ai:chat")),
    db: Session = Depends(get_db),
):
    """会话详情与全部消息（仅本人会话）。"""
    return ok(ai_chat_service.get_conversation(db, conversation_id, operator))


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    operator: SysUser = Depends(require_permissions("ai:chat")),
    db: Session = Depends(get_db),
):
    """删除会话（软删除）。"""
    ai_chat_service.delete_conversation(db, conversation_id, operator)
    return ok(message="删除成功")
