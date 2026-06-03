"""Agent 主控循环 — LLM 驱动的 Plan-then-Execute 循环

核心流程:
  用户输入 → System Prompt + Tool Schema → LLM 决策
    → 工具调用 → 执行 → 结果回传 → LLM 继续决策
    → ... 循环 → 最终输出

支持:
  - 多轮工具调用（search → plan → generate → evaluate → save）
  - 自动评分 + 不达标重试
  - 循环保护（max_steps）
  - Rich 终端美化输出
"""

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from src.llm.base import LLMProvider, Message, ToolCall, LLMResponse
from src.llm.factory import create_provider
from src.tools.registry import ToolRegistry, create_default_registry
from src.tools.handlers import (
    register_poem_handlers,
    register_search_handlers,
    register_storage_handlers,
)
from src.config.prompts import SYSTEM_PROMPT
from src.config import config

console = Console(force_terminal=False, legacy_windows=True)


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    output: str = ""
    steps: int = 0
    tool_calls_count: int = 0
    error: str = ""


class PoemController:
    """诗千家智能体主控制器

    使用方式:
        controller = PoemController()
        result = await controller.run("写一首关于春天的诗")
        print(result.output)
    """

    def __init__(
        self,
        llm: LLMProvider | None = None,
        registry: ToolRegistry | None = None,
        max_steps: int = 10,
    ):
        self._llm = llm
        self._registry = registry
        self.max_steps = max_steps

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = create_provider()
        return self._llm

    @property
    def registry(self) -> ToolRegistry:
        if self._registry is None:
            self._registry = self._build_registry()
        return self._registry

    def _build_registry(self) -> ToolRegistry:
        """构建并注册所有工具"""
        reg = create_default_registry()
        register_poem_handlers(reg)
        register_search_handlers(reg)
        register_storage_handlers(reg)
        return reg

    async def run(
        self,
        user_input: str,
        system_prompt: str | None = None,
        verbose: bool = True,
    ) -> AgentResult:
        """执行 Agent 主循环

        Args:
            user_input: 用户输入
            system_prompt: 自定义 system prompt，默认使用 prompts.SYSTEM_PROMPT
            verbose: 是否打印详细执行过程

        Returns:
            AgentResult
        """
        prompt = system_prompt or SYSTEM_PROMPT

        # 构建初始消息
        messages: list[Message] = [
            Message(role="system", content=prompt),
            Message(role="user", content=user_input),
        ]

        if verbose:
            console.print(Panel.fit(
                user_input,
                title="[bold blue]用户输入[/]",
                border_style="blue",
            ))

        tool_schemas = self.registry.get_all_schemas()
        tool_count = 0

        for step in range(1, self.max_steps + 1):
            if verbose:
                console.print(f"\n[dim]--- Step {step}/{self.max_steps} ---[/]")

            # 调用 LLM
            response = await self.llm.chat(
                messages=messages,
                tools=tool_schemas,
                temperature=0.7,
            )

            if response.finish_reason == "error":
                return AgentResult(
                    success=False,
                    steps=step,
                    tool_calls_count=tool_count,
                    error=response.content,
                )

            # 收到文本回复 → 结束
            if response.finish_reason == "stop" and response.content:
                if verbose:
                    console.print("\n[bold green]══════════ 最终输出 ══════════[/]")
                    console.print(Markdown(response.content))
                return AgentResult(
                    success=True,
                    output=response.content,
                    steps=step,
                    tool_calls_count=tool_count,
                )

            # 收到工具调用
            if response.tool_calls:
                # 追加 assistant 消息
                messages.append(Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                ))

                for tc in response.tool_calls:
                    tool_count += 1
                    if verbose:
                        console.print(
                            f"  [cyan]🔧 {tc.name}[/] "
                            f"[dim]{_format_args(tc.arguments)}[/]"
                        )

                    # 执行工具
                    exec_result = await self.registry.execute(tc.name, tc.arguments)

                    # 工具结果转字符串
                    result_text = _serialize_result(exec_result)

                    if verbose:
                        if exec_result.get("success"):
                            preview = result_text[:200].replace("\n", " ")
                            console.print(f"  [green]   ✓[/] [dim]{preview}...[/]")
                        else:
                            console.print(f"  [red]   ✗ {exec_result.get('error', '')}[/]")

                    # 追加 tool 消息
                    messages.append(Message(
                        role="tool",
                        content=result_text,
                        tool_call_id=tc.id,
                        name=tc.name,
                    ))

                continue

            # finish_reason == "stop" 但无 content → 强制要求回复
            if verbose:
                console.print("  [yellow]LLM 未返回内容，强制要求回复[/]")
            messages.append(Message(
                role="user",
                content="请继续。如果任务已完成，请给出最终结果。",
            ))

        # 超过最大步数
        messages.append(Message(
            role="user",
            content="已达到最大执行步数，请基于当前进展给出最终总结。",
        ))
        final_resp = await self.llm.chat(messages=messages)
        if verbose:
            console.print("\n[yellow]══════════ 超步数强制输出 ══════════[/]")
            console.print(Markdown(final_resp.content))
        return AgentResult(
            success=True,
            output=final_resp.content,
            steps=self.max_steps,
            tool_calls_count=tool_count,
        )


def _format_args(args: dict) -> str:
    """格式化工具参数显示"""
    import json

    s = json.dumps(args, ensure_ascii=False)
    if len(s) > 120:
        return s[:120] + "..."
    return s


def _serialize_result(result: dict) -> str:
    """将工具执行结果序列化为 LLM 可读的字符串"""
    import json

    if not result.get("success"):
        return f"错误: {result.get('error', '未知错误')}"

    data = result.get("result", result)
    # 去掉 success 字段，精简内容
    if isinstance(data, dict):
        data = {k: v for k, v in data.items() if k != "success"}

    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    # 限制长度避免超出 context
    if len(serialized) > 3000:
        serialized = serialized[:3000] + "\n...(结果已截断)"
    return serialized
