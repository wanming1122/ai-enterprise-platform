"""模型配置的请求体模型（M4-T1）。"""
from pydantic import BaseModel, field_validator

MODEL_TYPES = ("llm", "embedding", "rerank")
PROVIDERS = ("zhipu", "dashscope", "openai_compatible", "local")


class AIModelCreate(BaseModel):
    name: str
    model_type: str
    provider: str
    base_url: str | None = None
    api_key: str
    model_name: str
    temperature: float | None = None
    remark: str | None = None
    is_default: bool = False
    status: int = 1

    @field_validator("model_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in MODEL_TYPES:
            raise ValueError("模型类型需为 llm/embedding/rerank")
        return v

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, v: str) -> str:
        if v not in PROVIDERS:
            raise ValueError("服务商需为 zhipu/dashscope/openai_compatible/local")
        return v


class AIModelUpdate(BaseModel):
    """api_key 传 None 或空串表示保持原值。"""
    name: str | None = None
    model_type: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    remark: str | None = None
    is_default: bool | None = None
    status: int | None = None

    @field_validator("model_type")
    @classmethod
    def _check_type(cls, v: str | None) -> str | None:
        if v is not None and v not in MODEL_TYPES:
            raise ValueError("模型类型需为 llm/embedding/rerank")
        return v

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in PROVIDERS:
            raise ValueError("服务商需为 zhipu/dashscope/openai_compatible/local")
        return v
