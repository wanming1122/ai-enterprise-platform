"""找回密码流程集成测试：发码/限流/试错限次/过期/重置成功。"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.password_recovery_code import SysPasswordRecoveryCode
from app.models.user import SysUser
from app.services.auth_service import pwd_context
from app.services.password_recovery_service import reset_password, send_code

PASS = "NewPass123"


def _create_user(db, username: str, email: str | None = None) -> SysUser:
    user = SysUser(
        username=username, password_hash=pwd_context.hash("OldPass123"),
        nickname=username, status=1, email=email,
    )
    db.add(user)
    db.commit()
    return user


def _latest_record(db, user_id: int) -> SysPasswordRecoveryCode:
    return db.query(SysPasswordRecoveryCode).filter_by(user_id=user_id).order_by(
        SysPasswordRecoveryCode.id.desc()).first()


def test_send_code_demo_channel_returns_code(db_session):
    user = _create_user(db_session, "t_rc_send")
    data = send_code(db_session, user.username, "10.1.0.1")
    assert data["channel"] == "demo"
    assert data["code"] and len(data["code"]) == 6
    rec = _latest_record(db_session, user.id)
    assert rec is not None and rec.is_used == 0 and rec.expires_at > datetime.now()


def test_send_code_unknown_user_rejected(db_session):
    with pytest.raises(HTTPException) as exc:
        send_code(db_session, "ghost_user_xyz", "10.1.0.2")
    assert exc.value.status_code == 422
    assert "账号不存在" in exc.value.detail


def test_account_rate_limit_three_per_window(db_session):
    user = _create_user(db_session, "t_rc_limit")
    for _ in range(3):
        send_code(db_session, user.username, "10.1.0.3")
    with pytest.raises(HTTPException) as exc:
        send_code(db_session, user.username, "10.1.0.3")
    assert "频繁" in exc.value.detail


def test_reset_success_and_login_hash_changed(db_session):
    user = _create_user(db_session, "t_rc_reset")
    code = send_code(db_session, user.username, "10.1.0.4")["code"]
    reset_password(db_session, user.username, code, PASS)
    db_session.refresh(user)
    assert pwd_context.verify(PASS, user.password_hash)
    rec = _latest_record(db_session, user.id)
    assert rec.is_used == 1  # 用后作废，不可重放


def test_wrong_code_consumes_attempt(db_session):
    user = _create_user(db_session, "t_rc_wrong")
    code = send_code(db_session, user.username, "10.1.0.5")["code"]

    with pytest.raises(HTTPException) as exc:
        reset_password(db_session, user.username, "000000", PASS)
    assert "还可尝试 4 次" in exc.value.detail

    # 正确验证码仍可重置
    reset_password(db_session, user.username, code, PASS)
    db_session.refresh(user)
    assert pwd_context.verify(PASS, user.password_hash)


def test_expired_code_rejected(db_session):
    user = _create_user(db_session, "t_rc_expired")
    send_code(db_session, user.username, "10.1.0.6")
    rec = _latest_record(db_session, user.id)
    rec.expires_at = datetime.now() - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        reset_password(db_session, user.username, "123456", PASS)
    assert "过期" in exc.value.detail


def test_try_count_limit_locks_code(db_session):
    user = _create_user(db_session, "t_rc_trylimit")
    send_code(db_session, user.username, "10.1.0.7")
    rec = _latest_record(db_session, user.id)
    rec.try_count = 5  # 已达试错上限
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        reset_password(db_session, user.username, "123456", PASS)
    assert "次数过多" in exc.value.detail or "重新获取" in exc.value.detail


def test_reset_clears_lockout(db_session):
    """重置成功后清除登录失败计数与账号锁定。"""
    user = _create_user(db_session, "t_rc_unlock")
    user.failed_login_count = 5
    user.locked_until = datetime.now() + timedelta(minutes=10)
    db_session.commit()
    code = send_code(db_session, user.username, "10.1.0.8")["code"]

    reset_password(db_session, user.username, code, PASS)
    db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is None
