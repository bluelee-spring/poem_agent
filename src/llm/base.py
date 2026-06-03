"""LLM Provider 抽象基类

定义统一的 Message / LLMResponse / ToolCall 数据结构，
上层代码只依赖此接口，不感知具体模型 API。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """LLM 返回的工具调用指令"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """统一的 LLM 响应"""

    content: str = ""  # 文本回复（finish_reason="stop" 时有值）
    tool_calls: list[ToolCall] = field(default_factory=list)  # 工具调用（finish_reason="tool_calls" 时有值）
    finish_reason: str = ""  # "stop" | "tool_calls" | "length" | "error"
    usage: dict[str, int] = field(default_factory=dict)  # {"prompt": N, "completion": N, "total": N}
    model: str = ""  # 实际使用的模型名
    raw: Any = None  # 原始响应，调试用


@dataclass
class Message:
    """统一的消息格式，抹平不同 API 差异"""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] | None = None  # assistant 消息的工具调用
    tool_call_id: str | None = None  # tool 消息对应的 tool_call id
    name: str | None = None  # tool 消息的工具名

    def to_openai_format(self) -> dict:
        """转换为 OpenAI 兼容的消息格式"""
        msg: dict[str, Any] = {"role": self.role}

        if self.role == "tool":
            msg["tool_call_id"] = self.tool_call_id or ""
            msg["content"] = self.content
            return msg

        if self.content:
            msg["content"] = self.content

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": _safe_json_dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]

        if self.name:
            msg["name"] = self.name

        return msg


class LLMProvider(ABC):
    """LLM Provider 抽象基类

    所有 LLM 实现必须继承此类，实现 chat() 方法。
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """发送对话请求

        Args:
            messages: 对话历史
            tools: 工具定义列表（OpenAI function calling 格式）
            temperature: 采样温度
            max_tokens: 最大输出 token 数

        Returns:
            统一的 LLMResponse
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """当前使用的模型名"""
        ...


def _safe_json_dumps(obj: Any) -> str:
    """安全序列化为 JSON 字符串"""
    import json

    return json.dumps(obj, ensure_ascii=False)
