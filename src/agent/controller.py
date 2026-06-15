"""Agent 主控循环 — LLM 驱动的 Plan-then-Execute 循环

核心流程:
  用户输入 → 通用能力清单(System Prompt) → LLM 决策
    → 简单操作: 直接调 tool
    → 复杂工作流: 调用 use_skill(name) → 动态加载 Skill 完整 prompt + 限定 tools
    → ... 循环 → 最终输出

支持:
  - 按需加载 Skill（request → load → read → run）
  - 通用模式（全部 8 个 tools）与 Skill 模式（限定 tools）动态切换
  - 多轮工具调用 + 循环保护（max_steps）
  - Rich 终端美化输出
"""

from dataclasses import dataclass, field
from typing import Any, Optional

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
    register_metrics_handlers,
    register_skill_handlers,
)
from src.skills.base import Skill
from src.skills.registry import get_skill_registry
from src.config.prompts import SYSTEM_PROMPT, SHARED_CONTEXT
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

    两种模式:
      通用模式 (skill=None): 全部 tools + 轻量能力清单
        controller = PoemController()
        result = await controller.run("查看历史")

      Skill 模式 (skill=...): 限定 tools + 完整工作流 prompt
        skill = get_skill_registry().get("hot_topic_poem")
        controller = PoemController(skill=skill)
        result = await controller.run("写一首关于春天的诗")

    按需加载:
      LLM 也可以在对话中调用 use_skill("hot_topic_poem") 动态切换。
    """

    def __init__(
        self,
        skill: Skill | None = None,
        llm: LLMProvider | None = None,
        registry: ToolRegistry | None = None,
        max_steps: int = 10,
    ):
        self.skill = skill
        self._llm = llm
        self._registry = registry
        self.max_steps = max_steps
        self._skill_loaded = skill is not None
        self._messages: list[Message] = []       # 会话历史（持久化多轮对话）

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = create_provider()
        return self._llm

    async def _run_teardown(self) -> None:
        """执行 Skill 后置钩子（如果存在）"""
        if self.skill and self.skill.teardown:
            await self.skill.teardown()

    @property
    def registry(self) -> ToolRegistry:
        if self._registry is None:
            self._registry = self._build_registry()
        return self._registry

    def _build_registry(self) -> ToolRegistry:
        """构建并注册所有工具（通用模式：8 tools 含 use_skill）"""
        reg = create_default_registry()
        register_poem_handlers(reg)
        register_search_handlers(reg)
        register_storage_handlers(reg)
        register_metrics_handlers(reg)
        register_skill_handlers(reg)  # use_skill 元工具
        return reg

    def _build_system_prompt(self, system_prompt: str | None) -> str:
        """构建完整的 System Prompt

        如果已有 Skill 加载，注入共享知识 + Skill 完整 prompt。
        否则用通用能力清单 + 动态 Skill 列表。
        """
        from datetime import datetime
        now = datetime.now()
        date_info = (
            f"\n\n## 当前时间\n"
            f"现在是 {now.year} 年 {now.month} 月 {now.day} 日，"
            f"星期{'一二三四五六日'[now.weekday()]}，{now.strftime('%H:%M')}。"
            f"\n当前季节为{'春夏秋冬'[(now.month % 12) // 3]}季。"
            f"\n搜索热点、判断时令请以此时刻为基准。"
        )

        if self.skill:
            # Skill 模式：共享知识 + Skill 完整工作流
            return SHARED_CONTEXT + "\n\n" + self.skill.system_prompt + date_info

        # 通用模式：能力清单 + 动态 Skill 列表 + 共享知识
        prompt = system_prompt or SYSTEM_PROMPT

        # 注入可用 Skill 列表
        registry = get_skill_registry()
        skills = registry.list_details()
        if skills:
            rows = "\n".join(
                f"| {s['name']} | {s['description']} |"
                for s in skills
            )
            skills_table = (
                f"\n\n## 可用技能（调用 use_skill 按需加载）\n"
                f"| 技能名 | 用途 |\n|--------|------|\n{rows}\n\n"
            )
        else:
            skills_table = "\n\n## 可用技能\n暂无可用技能。\n\n"

        prompt = prompt.replace("replace_skills_section", skills_table)

        return prompt + SHARED_CONTEXT + date_info

    def _get_tool_schemas(self) -> list[dict]:
        """获取当前模式下的工具列表

        通用模式: 全部 tools（含 use_skill）
        Skill 模式: 仅 skill.tool_names 指定的 tools
        """
        all_schemas = self.registry.get_all_schemas()
        if self.skill:
            return [
                s for s in all_schemas
                if s["function"]["name"] in self.skill.tool_names
            ]
        return all_schemas

    async def _handle_use_skill(
        self,
        skill_name: str,
        messages: list[Message],
        verbose: bool,
    ) -> str:
        """处理 use_skill 调用：动态加载 Skill

        Returns:
            注入给 LLM 的 skill prompt 文本
        """
        registry = get_skill_registry()
        skill = registry.get(skill_name)

        if skill is None:
            return f"技能 '{skill_name}' 不存在。可用技能: {registry.list()}。请选择可用技能或直接使用通用工具完成用户请求。"

        # 加载 Skill
        self.skill = skill
        self._skill_loaded = True

        if verbose:
            console.print(
                f"  [bold magenta]⚡ Skill 已加载: {skill.name}[/] — {skill.description}"
            )

        # 运行 Skill 前置钩子
        if skill.setup:
            await skill.setup()

        # 构造注入消息：告知 LLM 新上下文
        injection = (
            f"✅ 技能「{skill.name}」已加载。以下是该技能的完整工作流指令，请严格遵循：\n\n"
            f"---\n"
            f"{SHARED_CONTEXT}\n\n"
            f"{skill.system_prompt}\n"
            f"---\n\n"
            f"注意：当前可用工具已切换为该技能的专用工具集，共 {len(skill.tool_names)} 个。"
        )

        return injection

    async def run(
        self,
        user_input: str,
        system_prompt: str | None = None,
        continue_session: bool = False,
        verbose: bool = True,
    ) -> AgentResult:
        """执行 Agent 主循环

        优先级: 显式 system_prompt > Skill.system_prompt > 默认 SYSTEM_PROMPT(含能力清单)

        Args:
            user_input: 用户输入
            system_prompt: 自定义 system prompt（覆盖所有默认值）
            continue_session: True=延续上一轮对话上下文，False=开启新会话
            verbose: 是否打印详细执行过程

        Returns:
            AgentResult
        """
        # 处理会话上下文
        if continue_session and self._messages:
            # 延续对话：system prompt 不变，只追加新用户消息
            messages = self._messages + [Message(role="user", content=user_input)]
            if verbose:
                skill_tag = f" [Skill: {self.skill.name}]" if self.skill else ""
                console.print(Panel.fit(
                    user_input,
                    title=f"[bold blue]用户输入（续）{skill_tag}[/]",
                    border_style="blue",
                ))
        else:
            # 新会话
            prompt = self._build_system_prompt(system_prompt)
            messages = [
                Message(role="system", content=prompt),
                Message(role="user", content=user_input),
            ]
            if verbose:
                skill_tag = f" [Skill: {self.skill.name}]" if self.skill else ""
                console.print(Panel.fit(
                    user_input,
                    title=f"[bold blue]用户输入{skill_tag}[/]",
                    border_style="blue",
                ))

        tool_schemas = self._get_tool_schemas()
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
                self._messages = messages
                await self._run_teardown()
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
                self._messages = messages
                await self._run_teardown()
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

                    # ---- use_skill 特殊处理 ----
                    if tc.name == "use_skill":
                        skill_name = tc.arguments.get("name", "")
                        result_text = await self._handle_use_skill(
                            skill_name, messages, verbose
                        )
                        # Skill 加载后，重新计算工具集
                        tool_schemas = self._get_tool_schemas()
                    else:
                        # 执行普通工具
                        exec_result = await self.registry.execute(tc.name, tc.arguments)
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
        self._messages = messages
        await self._run_teardown()
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
    if len(serialized) > 1500:
        serialized = serialized[:1500] + "\n...(结果已截断)"
    return serialized
