"""模型 API 密钥的 Fernet 对称加解密（M4-T1）。密钥来自 .env 的 FERNET_KEY。"""
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.core.config import settings


def _fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        raise HTTPException(status_code=422, detail="未配置 FERNET_KEY，无法加解密模型密钥")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"FERNET_KEY 无效：{exc}") from exc


def encrypt_api_key(plain: str) -> str:
    """明文 API Key → Fernet 密文（入库存储）。"""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_api_key(cipher: str) -> str:
    """Fernet 密文 → 明文 API Key（仅服务端调用外部 API 时使用，禁止返回前端）。"""
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(status_code=422, detail="API 密钥解密失败：FERNET_KEY 与加密时不一致") from exc


def mask_api_key(cipher: str) -> str:
    """密文 → 展示掩码：仅暴露明文后 4 位。"""
    try:
        plain = decrypt_api_key(cipher)
    except HTTPException:
        return "******"
    if len(plain) <= 4:
        return "****"
    return f"****{plain[-4:]}"
