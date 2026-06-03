"""OpenAI 兼容 Provider — 适用于 OpenAI / Azure / 本地模型等"""

import json
import httpx
from typing import Any

from src.llm.base import LLMProvider, LLMResponse, Message, ToolCall


class OpenAIProvider(LLMProvider):
    """OpenAI 兼容 API 适配器

    适用于:
      - OpenAI (api.openai.com)
      - Azure OpenAI
      - 本地模型 (Ollama / vLLM / LocalAI / LM Studio ...)
      - 中转代理
    """

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client: httpx.AsyncClient | None = None

    @property
    def model_name(self) -> str:
        return self._model

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        client = await self._get_client()

        body: dict[str, Any] = {
            "model": self._model,
            "messages": [msg.to_openai_format() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            resp = await client.post("/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_response(data)
        except httpx.HTTPStatusError as e:
            return LLMResponse(
                finish_reason="error",
                content=f"HTTP {e.response.status_code}: {e.response.text[:500]}",
                model=self._model,
            )
        except Exception as e:
            return LLMResponse(
                finish_reason="error",
                content=str(e),
                model=self._model,
            )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _parse_response(self, data: dict) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")

        content = message.get("content", "") or ""

        tool_calls = []
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {"_raw": args_str}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=args,
                )
            )

        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
            model=data.get("model", self._model),
            raw=data,
        )
