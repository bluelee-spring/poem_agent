"""Skill 层 — 可插拔的 Agent 工作流

每个 Skill 封装一个完整的工作流：
  - system_prompt：告诉 LLM 如何完成任务
  - tool_names：需要的工具子集
  - setup / teardown：可选的前后置钩子

目录结构:
  base.py      → Skill 基类
  registry.py  → Skill 注册中心
  hot_topic_poem/ → 热点写诗 Skill
"""

from src.skills.base import Skill
from src.skills.registry import SkillRegistry, get_skill_registry

__all__ = [
    "Skill",
    "SkillRegistry",
    "get_skill_registry",
]
