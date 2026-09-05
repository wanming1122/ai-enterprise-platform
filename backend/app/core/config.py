"""全局配置：从 backend/.env 读取，密钥严禁硬编码于代码。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # 存储目录
    MEDIA_DIR: str = "./media"
    CHROMA_DIR: str = "./data/chroma"

    # 模型 API（通过 .env 注入，严禁硬编码真实密钥）
    ZHIPU_API_KEY: str = ""
    MIMO_BASE_URL: str = ""
    MIMO_API_KEY: str = ""
    MIMO_MODEL: str = "MiMo-V2.5"          # 生成模型（OpenAI兼容 chat）
    MIMO_EMBEDDING_MODEL: str = "text-embedding-v3"  # 向量模型（MiMo官方无embeddings时由服务商提供）

    @property
    def database_url(self) -> str:
        """MySQL 连接串（utf8mb4）。"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()