from __future__ import annotations

"""Skill 基类 — 可插拔的 Agent 工作流抽象

每个 Skill 定义了一个完整的工作流：
  - description：一行描述，注入通用 System Prompt 的「能力清单」
  - system_prompt：完整工作流指令，LLM 调用 use_skill 后按需加载
  - tool_names：需要的工具子集（加载后限定）
  - references：可选引用的数据文件路径（read 阶段）
  - setup / teardown：可选的前/后置钩子

按需加载链路：
  request(能力清单) → load(完整 SKILL.md) → read(references) → run(scripts)
"""

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional


@dataclass
class Skill:
    """一个可插拔的 Agent 工作流

    Attributes:
        name: 技能名称，如 "hot_topic_poem"
        description: 一行描述，注入通用 Prompt 的能力清单（request 阶段）
        system_prompt: 完整工作流指令（load 阶段按需注入）
        tool_names: 该技能需要的工具名称列表（加载后限定可用工具）
        references: 可选引用的数据文件路径列表（read 阶段，如韵部表）
        setup: 可选的前置钩子（异步），在 Skill 加载时调用
        teardown: 可选的后置钩子（异步），在 Agent 返回前调用
    """
    name: str
    description: str
    system_prompt: str
    tool_names: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    setup: Optional[Callable[[], Awaitable[None]]] = None
    teardown: Optional[Callable[[], Awaitable[None]]] = None
