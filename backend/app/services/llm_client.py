"""生成模型客户端（M3，M4-T1 起模型配置优先）：OpenAI 兼容接口，流式/一次性对话。

reasoning_content 为推理型模型的思考增量，与正文分开产出，由调用方决定是否下发。
模型来源：ai_model 启用的默认生成配置优先，无则回退 .env 的 MIMO_*。
"""
import json

import httpx
from fastapi import HTTPException

from app.services import ai_model_service


def _base() -> tuple[str, str, str]:
    cfg = ai_model_service.resolve_llm_config()
    return cfg["base_url"], cfg["api_key"], cfg["model_name"]


def chat_stream(messages: list[dict], *, max_tokens: int = 2048, temperature: float = 0.3):
    """流式对话：yield (kind, delta)，kind ∈ reasoning|content。"""
    base, key, model = _base()
    with httpx.Client(timeout=httpx.Timeout(10, read=180)) as client:
        with client.stream(
            "POST",
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        ) as r:
            if r.status_code != 200:
                body = r.read().decode("utf-8", errors="ignore")
                raise HTTPException(status_code=422, detail=f"生成模型调用失败：{body[:200]}")
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if not data or data == "[DONE]":
                    if data == "[DONE]":
                        break
                    continue
                try:
                    delta = json.loads(data)["choices"][0].get("delta", {})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta.get("reasoning_content"):
                    yield "reasoning", delta["reasoning_content"]
                if delta.get("content"):
                    yield "content", delta["content"]


def chat_once(messages: list[dict], *, max_tokens: int = 512, temperature: float = 0.2) -> str:
    """一次性对话：返回正文内容（推理型模型返回思考过程时视为空）。"""
    base, key, model = _base()
    with httpx.Client(timeout=httpx.Timeout(10, read=180)) as client:
        r = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        if r.status_code != 200:
            raise HTTPException(status_code=422, detail=f"生成模型调用失败：{r.text[:200]}")
        message = r.json()["choices"][0]["message"]
        return (message.get("content") or "").strip()


def chat_with_tools(
    messages: list[dict], tools: list[dict], *, max_tokens: int = 2048, temperature: float = 0.2
) -> dict:
    """带工具定义的一次性对话：返回 OpenAI 格式 message dict。

    推理型模型回放 tool_calls 时必须携带 reasoning_content（否则接口报错），调用方把
    本函数返回的 dict 原样放回 messages 即可满足；tool_calls 结构原样透传。
    """
    base, key, model = _base()
    with httpx.Client(timeout=httpx.Timeout(10, read=180)) as client:
        r = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        if r.status_code != 200:
            raise HTTPException(status_code=422, detail=f"生成模型调用失败：{r.text[:200]}")
        message = r.json()["choices"][0]["message"]
        out: dict = {"role": "assistant", "content": message.get("content") or ""}
        if message.get("reasoning_content"):
            out["reasoning_content"] = message["reasoning_content"]
        if message.get("tool_calls"):
            out["tool_calls"] = message["tool_calls"]
        return out
