"""生成模型客户端（M3，M4-T1 起模型配置优先）：OpenAI 兼容接口，流式/一次性对话。

reasoning_content 为推理型模型的思考增量，与正文分开产出，由调用方决定是否下发。
模型来源：ai_model 启用的默认配置优先（或按 model_id 指定），无则回退 .env 的 MIMO_*。

M10 增强：
- 模型配置的 temperature 生效：调用方未显式传温时使用配置值，再回退各函数内置默认；
- 上游错误自动重试 1 次（连接异常 / 429 / 5xx / 1305 访问量过大，且流式尚未产出字节时）；
- 错误信息友好化：解析上游 JSON 错误码（如 1305）转为可读提示，不再裸抛 JSON；
- async 变体（achat_*）：供 AI 助手异步 SSE 链路使用，客户端断连时可被真正取消；
  同步版本保留给知识库问答 / NL2SQL / 后台任务。
"""
import json

import httpx
from fastapi import HTTPException

from app.services import ai_model_service

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _cfg(model_id: int | None = None) -> dict:
    return ai_model_service.resolve_llm_config(model_id)


def _base(model_id: int | None = None) -> tuple[str, str, str]:
    cfg = _cfg(model_id)
    return cfg["base_url"], cfg["api_key"], cfg["model_name"]


def _effective_temperature(temperature: float | None, cfg: dict, default: float) -> float:
    """温度优先级：调用方显式传入 > 模型配置 > 函数内置默认。"""
    if temperature is not None:
        return temperature
    cfg_temp = cfg.get("temperature")
    return float(cfg_temp) if cfg_temp is not None else default


def _friendly_error(body: str) -> str:
    """解析上游错误响应为友好提示（裸 JSON 不再直接透给用户）。"""
    text = body or ""
    code = ""
    try:
        data = json.loads(text)
        err = data.get("error") or {}
        code = str(err.get("code") or "")
        msg = str(err.get("message") or text)
    except (json.JSONDecodeError, AttributeError):
        msg = text
    if code == "1305" or "访问量过大" in msg or "busy" in msg.lower():
        return "生成模型繁忙，请稍后重试，或在右下角切换其他模型"
    return f"生成模型调用失败：{msg[:150]}"


def _retryable(status: int | None, body: str) -> bool:
    return (status is not None and status in _RETRYABLE_STATUS) or "1305" in (body or "")


# ---------- 思考模式控制（智谱 GLM 等） ----------

# 仅智谱 OpenAI 兼容端点支持 thinking.type；其余提供方不传（靠 max_tokens 兜底）
_THINKING_PROVIDERS = {"zhipu"}


def _thinking_field(cfg: dict, thinking: bool | None) -> dict:
    """思考模式控制参数：thinking=None 或提供方不支持时返回空（保持上游默认）。

    推理型模型会把思考算进 max_tokens，思考吃满预算时正文为空；关闭后（非深度思考）
    可把预算留给正文，显著降低"只出思考不出答案"的概率。
    """
    if thinking is None or str(cfg.get("provider") or "") not in _THINKING_PROVIDERS:
        return {}
    return {"thinking": {"type": "enabled" if thinking else "disabled"}}


def _extract_stream_error(chunk: dict) -> str | None:
    """SSE 数据块内嵌的 error（部分网关在 HTTP 200 流中回传失败）。

    此前被静默忽略，表现为"空回答"；显式识别后转为可读错误。
    """
    err = chunk.get("error")
    if not err:
        return None
    return _friendly_error(json.dumps(chunk, ensure_ascii=False))


# ---------- 同步版本（知识库问答 / NL2SQL / 后台任务） ----------


def chat_stream(messages: list[dict], *, max_tokens: int = 2048, temperature: float | None = None,
                model_id: int | None = None):
    """流式对话：yield (kind, delta)，kind ∈ reasoning|content|usage。

    usage 为最后一个携带 usage 的 chunk（部分兼容端点才下发）；未下发时调用方自行估算。
    """
    cfg = _cfg(model_id)
    base, key, model = cfg["base_url"], cfg["api_key"], cfg["model_name"]
    temp = _effective_temperature(temperature, cfg, 0.3)
    with httpx.Client(timeout=httpx.Timeout(10, read=120)) as client:
        with client.stream(
            "POST",
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "stream": True,
                  "max_tokens": max_tokens, "temperature": temp},
        ) as r:
            if r.status_code != 200:
                body = r.read().decode("utf-8", errors="ignore")
                raise HTTPException(status_code=422, detail=_friendly_error(body))
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if not data or data == "[DONE]":
                    if data == "[DONE]":
                        break
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                usage = payload.get("usage")
                if usage and usage.get("total_tokens") is not None:
                    yield "usage", usage
                    continue
                try:
                    delta = payload["choices"][0].get("delta", {})
                except (KeyError, IndexError):
                    continue
                if delta.get("reasoning_content"):
                    yield "reasoning", delta["reasoning_content"]
                if delta.get("content"):
                    yield "content", delta["content"]


def _parse_message(r: httpx.Response, usage_out: dict | None) -> dict:
    """解析一次性对话响应为 OpenAI 格式 message dict（并回填 usage）。"""
    body = r.json()
    if usage_out is not None and body.get("usage"):
        usage_out.update(body["usage"])
    message = body["choices"][0]["message"]
    out: dict = {"role": "assistant", "content": message.get("content") or ""}
    if message.get("reasoning_content"):
        out["reasoning_content"] = message["reasoning_content"]
    if message.get("tool_calls"):
        out["tool_calls"] = message["tool_calls"]
    return out


def chat_once(
    messages: list[dict], *, max_tokens: int = 512, temperature: float | None = None,
    usage_out: dict | None = None, model_id: int | None = None,
) -> str:
    """一次性对话：返回正文内容。可重试错误自动重试一次。"""
    cfg = _cfg(model_id)
    base, key, model = cfg["base_url"], cfg["api_key"], cfg["model_name"]
    temp = _effective_temperature(temperature, cfg, 0.2)
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temp}
    last_err: str | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=httpx.Timeout(10, read=120)) as client:
                r = client.post(f"{base}/chat/completions",
                                headers={"Authorization": f"Bearer {key}"}, json=payload)
            if r.status_code == 200:
                return (_parse_message(r, usage_out).get("content") or "").strip()
            last_err = _friendly_error(r.text)
            if not (attempt == 0 and _retryable(r.status_code, r.text)):
                break
        except httpx.HTTPError as exc:
            last_err = f"连接生成模型失败：{exc}"
            if attempt == 1:
                break
    raise HTTPException(status_code=422, detail=last_err or "生成模型调用失败")


def chat_with_tools(
    messages: list[dict], tools: list[dict], *, max_tokens: int = 2048, temperature: float | None = None,
    usage_out: dict | None = None, model_id: int | None = None,
) -> dict:
    """带工具定义的一次性对话：返回 OpenAI 格式 message dict。

    推理型模型回放 tool_calls 时必须携带 reasoning_content（否则接口报错），调用方把
    本函数返回的 dict 原样放回 messages 即可满足。可重试错误自动重试一次。
    """
    cfg = _cfg(model_id)
    base, key, model = cfg["base_url"], cfg["api_key"], cfg["model_name"]
    temp = _effective_temperature(temperature, cfg, 0.2)
    payload = {"model": model, "messages": messages, "tools": tools,
               "max_tokens": max_tokens, "temperature": temp}
    last_err: str | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=httpx.Timeout(10, read=120)) as client:
                r = client.post(f"{base}/chat/completions",
                                headers={"Authorization": f"Bearer {key}"}, json=payload)
            if r.status_code == 200:
                return _parse_message(r, usage_out)
            last_err = _friendly_error(r.text)
            if not (attempt == 0 and _retryable(r.status_code, r.text)):
                break
        except httpx.HTTPError as exc:
            last_err = f"连接生成模型失败：{exc}"
            if attempt == 1:
                break
    raise HTTPException(status_code=422, detail=last_err or "生成模型调用失败")
# ---------- 异步版本（AI 助手 SSE：断连可真正取消 LLM 调用） ----------


async def achat_stream(messages: list[dict], *, max_tokens: int = 2048, temperature: float | None = None,
                       model_id: int | None = None, thinking: bool | None = None):
    """achat_stream：yield (kind, delta)，kind ∈ reasoning|content|usage。语义同 chat_stream。

    连接失败/可重试错误在尚未产出字节时自动重试一次；已产出增量后断流则直接报错（防重复内容）。
    thinking 控制上游思考模式（仅智谱端点生效，None=保持默认）；模型不支持该参数时自动去掉重试。
    """
    cfg = _cfg(model_id)
    base, key, model = cfg["base_url"], cfg["api_key"], cfg["model_name"]
    temp = _effective_temperature(temperature, cfg, 0.3)
    payload = {"model": model, "messages": messages, "stream": True,
               "max_tokens": max_tokens, "temperature": temp}
    thinking_field = _thinking_field(cfg, thinking)
    # 候选请求体：优先带思考控制；上游以 4xx 拒绝该参数时自动降级为不带
    bodies = [{**payload, **thinking_field}, payload] if thinking_field else [payload]
    last_err: str | None = None
    for body in bodies:
        for attempt in range(2):  # 同一请求体内：瞬时错误（连接/429/5xx）且未产出时重试一次
            produced = False
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=120)) as client:
                    async with client.stream(
                        "POST",
                        f"{base}/chat/completions",
                        headers={"Authorization": f"Bearer {key}"},
                        json=body,
                    ) as r:
                        if r.status_code != 200:
                            raw = (await r.aread()).decode("utf-8", errors="ignore")
                            last_err = _friendly_error(raw)
                            if attempt == 0 and _retryable(r.status_code, raw):
                                continue  # 尚未产出字节，安全重试
                            break  # 该请求体不可用：尝试下一个变体（或最终报错）
                        async for line in r.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[len("data:"):].strip()
                            if not data or data == "[DONE]":
                                if data == "[DONE]":
                                    break
                                continue
                            try:
                                payload_chunk = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            # 200 流中内嵌的 error 块：显式抛出，避免被误判为"空回答"
                            stream_err = _extract_stream_error(payload_chunk)
                            if stream_err:
                                raise HTTPException(status_code=422, detail=stream_err)
                            usage = payload_chunk.get("usage")
                            if usage and usage.get("total_tokens") is not None:
                                produced = True
                                yield "usage", usage
                                continue
                            try:
                                delta = payload_chunk["choices"][0].get("delta", {})
                            except (KeyError, IndexError):
                                continue
                            if delta.get("reasoning_content") or delta.get("content"):
                                produced = True
                            if delta.get("reasoning_content"):
                                yield "reasoning", delta["reasoning_content"]
                            if delta.get("content"):
                                yield "content", delta["content"]
                        return
            except httpx.HTTPError as exc:
                # 已产出增量后中途断流：不重试（防内容重复），直接报错
                last_err = f"连接生成模型失败：{exc}"
                if produced or attempt == 1:
                    raise HTTPException(status_code=422, detail=last_err)
                continue
    raise HTTPException(status_code=422, detail=last_err or "生成模型调用失败")


async def achat_once(
    messages: list[dict], *, max_tokens: int = 512, temperature: float | None = None,
    usage_out: dict | None = None, model_id: int | None = None,
) -> str:
    """achat_once：语义同 chat_once（可重试错误自动重试一次）。"""
    cfg = _cfg(model_id)
    base, key, model = cfg["base_url"], cfg["api_key"], cfg["model_name"]
    temp = _effective_temperature(temperature, cfg, 0.2)
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temp}
    last_err: str | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=120)) as client:
                r = await client.post(f"{base}/chat/completions",
                                      headers={"Authorization": f"Bearer {key}"}, json=payload)
            if r.status_code == 200:
                return (_parse_message(r, usage_out).get("content") or "").strip()
            last_err = _friendly_error(r.text)
            if not (attempt == 0 and _retryable(r.status_code, r.text)):
                break
        except httpx.HTTPError as exc:
            last_err = f"连接生成模型失败：{exc}"
            if attempt == 1:
                break
    raise HTTPException(status_code=422, detail=last_err or "生成模型调用失败")


async def achat_with_tools(
    messages: list[dict], tools: list[dict], *, max_tokens: int = 2048, temperature: float | None = None,
    usage_out: dict | None = None, model_id: int | None = None, thinking: bool | None = None,
) -> dict:
    """achat_with_tools：语义同 chat_with_tools（可重试错误自动重试一次）。

    thinking 控制上游思考模式（仅智谱端点生效，None=保持默认）；模型不支持该参数时自动去掉重试。
    """
    cfg = _cfg(model_id)
    base, key, model = cfg["base_url"], cfg["api_key"], cfg["model_name"]
    temp = _effective_temperature(temperature, cfg, 0.2)
    payload = {"model": model, "messages": messages, "tools": tools,
               "max_tokens": max_tokens, "temperature": temp}
    thinking_field = _thinking_field(cfg, thinking)
    bodies = [{**payload, **thinking_field}, payload] if thinking_field else [payload]
    last_err: str | None = None
    for body in bodies:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=120)) as client:
                    r = await client.post(f"{base}/chat/completions",
                                          headers={"Authorization": f"Bearer {key}"}, json=body)
                if r.status_code == 200:
                    return _parse_message(r, usage_out)
                last_err = _friendly_error(r.text)
                if attempt == 0 and _retryable(r.status_code, r.text):
                    continue
                break  # 该请求体不可用：尝试下一个变体（去掉思考控制）
            except httpx.HTTPError as exc:
                last_err = f"连接生成模型失败：{exc}"
                if attempt == 1:
                    break
                continue
    raise HTTPException(status_code=422, detail=last_err or "生成模型调用失败")
