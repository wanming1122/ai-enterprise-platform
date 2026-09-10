"""全局配置：从 backend/.env 读取，密钥严禁硬编码于代码。"""
import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "enterprise"

    # JWT
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # 是否信任反向代理的 X-Forwarded-For 头（仅在部署于可信代理之后时开启）
    TRUST_XFF: bool = False

    # 模型密钥 Fernet 对称加密密钥（ai_model.api_key 加密存储）
    FERNET_KEY: str = ""

    # 存储目录
    MEDIA_DIR: str = "./media"
    CHROMA_DIR: str = "./data/chroma"

    # AI 助手默认模型上下文窗口（token，启发式估算用；可在 .env 覆盖）
    CONTEXT_WINDOW_TOKENS: int = 32768

    # SMTP 邮件（找回密码验证码下发；留空则走演示回显模式）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""  # 发件人，缺省用 SMTP_USER

    # 模型 API（通过 .env 注入，严禁硬编码真实密钥）
    ZHIPU_API_KEY: str = ""
    MIMO_BASE_URL: str = ""
    MIMO_API_KEY: str = ""
    MIMO_MODEL: str = "MiMo-V2.5"          # 生成模型（OpenAI兼容 chat）
    MIMO_EMBEDDING_MODEL: str = "text-embedding-v3"  # 向量模型（MiMo官方无embeddings时由服务商提供）

    # MCP Server：是否对外暴露 server_admin 工具（检索/查数默认提供；该工具为只读沙箱探查）
    MCP_ENABLE_SERVER_ADMIN: bool = True

    @property
    def database_url(self) -> str:
        """MySQL 连接串（utf8mb4）。"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # 安全兜底：默认/弱密钥不可用于签发令牌（任何人可用公开默认值伪造任意用户）。
    # 检测到时自动换用进程级随机密钥（重启后旧令牌全部失效，需重新登录），并大声告警。
    if not s.JWT_SECRET or s.JWT_SECRET == "change-me" or len(s.JWT_SECRET) < 16:
        logger.error(
            "JWT_SECRET 未配置或过弱！已自动使用随机临时密钥（重启后所有令牌失效）。"
            "请在 backend/.env 中配置强随机密钥，例如："
            f"JWT_SECRET={secrets.token_hex(32)}"
        )
        s.JWT_SECRET = secrets.token_hex(32)
    return s


settings = get_settings()