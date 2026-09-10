"""密码找回服务：验证码生成/校验/重置，含账号与 IP 双维度限流。

安全边界（设计方案 9.3）：验证码仅存 bcrypt 哈希、有效期 10 分钟；单账号 15 分钟内
最多 3 次发送、单 IP 15 分钟内最多 10 次；验证码最多试错 5 次，超次后作废需重新获取。
演示环境未接入邮件/短信服务，验证码在响应中直接回显（仅演示用途）。
"""
import secrets
import smtplib
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText

from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.password_recovery_code import SysPasswordRecoveryCode
from app.models.user import SysUser
from app.services.operation_log_service import write_log
from app.services.user_service import validate_password

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

CODE_TTL_MINUTES = 10        # 验证码有效期
SEND_WINDOW_MINUTES = 15     # 限流统计窗口
MAX_SEND_PER_ACCOUNT = 3     # 单账号窗口内发送上限
MAX_SEND_PER_IP = 10         # 单 IP 窗口内发送上限（进程内计数，重启清空）
MAX_TRY_COUNT = 5            # 单个验证码最大试错次数

_ip_send: dict[str, dict] = {}


def _reject(detail: str) -> None:
    raise HTTPException(status_code=422, detail=detail)


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:2]}***@{domain}" if len(local) > 2 else f"{local[0]}***@{domain}"


def _send_code_email(to_email: str, code: str) -> None:
    """SMTP 下发验证码邮件：465 走 SSL，其余端口走 STARTTLS。失败抛异常由调用方回退。"""
    msg = MIMEText(
        f"您正在找回企业管理系统账号的登录密码。\n\n验证码：{code}（{CODE_TTL_MINUTES} 分钟内有效）\n\n"
        f"若非本人操作，请忽略本邮件并注意账号安全。",
        "plain", "utf-8",
    )
    msg["Subject"] = Header("企业管理系统 - 找回密码验证码", "utf-8")
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    if settings.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        server.starttls()
    try:
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    finally:
        server.quit()


def _check_ip_limit(ip: str) -> None:
    """IP 维度发送限流（与登录失败锁定同一进程内计数模式）。

    锁定到期后清零计数：否则一次超限后每次请求都会续锁，
    该 IP 将退化为「每 15 分钟只能发 1 码」的准永久限流。
    """
    now = datetime.now()
    rec = _ip_send.get(ip)
    if rec and rec.get("lock_until"):
        if rec["lock_until"] > now:
            remain = max(1, int((rec["lock_until"] - now).total_seconds() // 60))
            _reject(f"操作过于频繁，请 {remain} 分钟后重试")
        rec["count"] = 0
        rec["lock_until"] = None
    rec = _ip_send.setdefault(ip, {"count": 0, "lock_until": None})
    rec["count"] += 1
    if rec["count"] >= MAX_SEND_PER_IP:
        rec["lock_until"] = now + timedelta(minutes=SEND_WINDOW_MINUTES)


def send_code(db: Session, username: str, ip: str) -> dict:
    """为账号生成找回验证码：限流检查 → 作废旧码 → 存哈希。返回验证码（演示回显）。"""
    now = datetime.now()
    _check_ip_limit(ip)

    user = db.scalar(select(SysUser).where(SysUser.username == username, SysUser.status != 2))
    if user is None:
        # 已配置 SMTP（真实发信）时不暴露账号是否存在，防枚举；演示回显模式维持明确报错
        if settings.SMTP_HOST:
            _reject("若该账号存在，验证码已发送至其绑定邮箱，请注意查收")
        _reject("账号不存在")

    sent = db.scalar(
        select(func.count()).select_from(SysPasswordRecoveryCode).where(
            SysPasswordRecoveryCode.user_id == user.id,
            SysPasswordRecoveryCode.created_at >= now - timedelta(minutes=SEND_WINDOW_MINUTES),
        )
    ) or 0
    if sent >= MAX_SEND_PER_ACCOUNT:
        _reject(f"验证码发送过于频繁，15 分钟内最多 {MAX_SEND_PER_ACCOUNT} 次")

    # 旧未使用验证码一律作废，同一时间仅一个有效码
    for rec in db.scalars(
        select(SysPasswordRecoveryCode).where(
            SysPasswordRecoveryCode.user_id == user.id, SysPasswordRecoveryCode.is_used == 0
        )
    ):
        rec.is_used = 1

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    db.add(SysPasswordRecoveryCode(
        user_id=user.id,
        code_hash=pwd_context.hash(code),
        expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
    ))
    db.commit()
    write_log(db, user_id=user.id, username=user.username, module="认证",
              action="申请找回密码", ip=ip, result=1)

    # 真实下发：SMTP 已配置且账号登记了邮箱；否则回退演示回显（未接渠道的环境）
    email = (user.email or "").strip()
    if _smtp_configured() and email:
        try:
            _send_code_email(email, code)
        except Exception as exc:
            write_log(db, user_id=user.id, username=user.username, module="认证",
                      action="找回密码邮件发送失败", result=0, error_message=str(exc)[:200])
            return {"code": code, "expires_in_minutes": CODE_TTL_MINUTES,
                    "channel": "demo", "email": None,
                    "note": "邮件发送失败，已回退演示回显"}
        return {"code": None, "expires_in_minutes": CODE_TTL_MINUTES,
                "channel": "email", "email": _mask_email(email)}
    return {"code": code, "expires_in_minutes": CODE_TTL_MINUTES, "channel": "demo", "email": None}


def reset_password(db: Session, username: str, code: str, new_password: str) -> None:
    """校验验证码并重置密码：过期/超次/错误均拒绝，成功后清除锁定与强制改密标记。"""
    now = datetime.now()
    user = db.scalar(select(SysUser).where(SysUser.username == username, SysUser.status != 2))
    if user is None:
        _reject("账号不存在")
    validate_password(new_password)

    rec = db.scalar(
        select(SysPasswordRecoveryCode)
        .where(SysPasswordRecoveryCode.user_id == user.id, SysPasswordRecoveryCode.is_used == 0)
        .order_by(SysPasswordRecoveryCode.id.desc())
    )
    if rec is None:
        _reject("请先获取验证码")
    if rec.expires_at is None or rec.expires_at < now:
        rec.is_used = 1
        db.commit()
        _reject("验证码已过期，请重新获取")
    if rec.try_count >= MAX_TRY_COUNT:
        rec.is_used = 1
        db.commit()
        write_log(db, user_id=user.id, username=user.username, module="认证",
                  action="找回密码失败", result=0, error_message="验证码试错超限")
        _reject("验证码错误次数过多，请重新获取")

    rec.try_count += 1
    db.commit()
    if not pwd_context.verify(code, rec.code_hash):
        remain = MAX_TRY_COUNT - rec.try_count
        write_log(db, user_id=user.id, username=user.username, module="认证",
                  action="找回密码失败", result=0, error_message="验证码错误")
        _reject(f"验证码错误，还可尝试 {remain} 次")

    rec.is_used = 1
    user.password_hash = pwd_context.hash(new_password)
    user.need_reset_pwd = 0
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    write_log(db, user_id=user.id, username=user.username, module="认证",
              action="找回密码重置", result=1)
