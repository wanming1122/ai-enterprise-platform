"""AI 助手会话管理（M7）：重命名、置顶、列表排序、越权与参数校验。"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.ai import AIConversation
from app.models.user import SysUser
from app.services import ai_chat_service


def _conv(db, user_id: int, title: str, updated_at: datetime) -> AIConversation:
    c = AIConversation(
        user_id=user_id, title=title, source="ai", pinned=0,
        created_at=updated_at, updated_at=updated_at,
    )
    db.add(c)
    db.commit()
    return c


def test_rename_and_pin_service(client, db_session):
    """重命名与置顶生效，列表排序置顶优先、组内按 updated_at 倒序。"""
    admin = db_session.query(SysUser).filter_by(username="admin").one()
    old = _conv(db_session, admin.id, "旧会话", datetime.now() - timedelta(days=2))
    recent = _conv(db_session, admin.id, "新会话", datetime.now())

    # 未置顶：新会话在前
    titles = [c["title"] for c, _ in [  # 仅取当前用户列表校验
    ]]
    items, _ = ai_chat_service.list_conversations(db_session, user_id=admin.id)
    assert [c["title"] for c in items][:2] == ["新会话", "旧会话"]
    assert all(c["pinned"] is False for c in items[:2])

    # 置顶旧会话：置顶优先排到首位
    updated = ai_chat_service.update_conversation(
        db_session, old.id, admin, pinned=True,
    )
    assert updated["pinned"] is True
    items, _ = ai_chat_service.list_conversations(db_session, user_id=admin.id)
    assert items[0]["id"] == old.id
    assert items[0]["pinned"] is True

    # 重命名
    renamed = ai_chat_service.update_conversation(
        db_session, old.id, admin, title="重命名后",
    )
    assert renamed["title"] == "重命名后"
    conv = db_session.get(AIConversation, old.id)
    assert conv.title == "重命名后"
    assert conv.pinned == 1


def test_update_conversation_validation_and_ownership(db_session):
    """无可更新字段 422；他人会话 404（越权不可见）。"""
    admin = db_session.query(SysUser).filter_by(username="admin").one()
    conv = _conv(db_session, admin.id, "我的会话", datetime.now())

    with pytest.raises(HTTPException) as exc:
        ai_chat_service.update_conversation(db_session, conv.id, admin, title=None, pinned=None)
    assert exc.value.status_code == 422

    # 另一用户（不存在该会话归属）视为 404
    stranger = SysUser(
        username="t_stranger", password_hash="x", nickname="t", status=1,
    )
    db_session.add(stranger)
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        ai_chat_service.update_conversation(db_session, conv.id, stranger, pinned=True)
    assert exc.value.status_code == 404


def test_http_patch_rename_and_pin(client, db_session, admin_headers):
    """HTTP PATCH：重命名与置顶返回并落库，列表响应带 pinned。"""
    admin = db_session.query(SysUser).filter_by(username="admin").one()
    conv = _conv(db_session, admin.id, "待改名", datetime.now())

    res = client.patch(
        f"/api/v1/ai/conversations/{conv.id}",
        json={"title": "新标题"}, headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["title"] == "新标题"
    assert res.json()["data"]["pinned"] is False

    res = client.patch(
        f"/api/v1/ai/conversations/{conv.id}",
        json={"pinned": True}, headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["pinned"] is True

    # 列表首条为该会话且带 pinned
    lst = client.get("/api/v1/ai/conversations", params={"page": 1, "page_size": 20}, headers=admin_headers)
    assert lst.status_code == 200, lst.text
    data = lst.json()["data"]
    assert data["list"][0]["id"] == conv.id
    assert data["list"][0]["pinned"] is True

    # 空 body / 空字段名 → 422
    res = client.patch(f"/api/v1/ai/conversations/{conv.id}", json={}, headers=admin_headers)
    assert res.status_code == 422
