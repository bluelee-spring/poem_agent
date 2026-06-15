"""Skill 注册中心 — 管理所有已注册的 Skill"""

from __future__ import annotations

from typing import Optional
from src.skills.base import Skill


class SkillRegistry:
    """Skill 注册中心

    使用方式:
        registry = SkillRegistry()
        registry.register(hot_topic_poem_skill)
        skill = registry.get("hot_topic_poem")
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """注册一个 Skill"""
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' 已注册")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        """获取指定 Skill"""
        return self._skills.get(name)

    def list(self) -> list[str]:
        """列出所有已注册的 Skill 名称"""
        return list(self._skills.keys())

    def list_details(self) -> list[dict]:
        """列出所有 Skill 的名称和描述"""
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
        ]

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills


# 全局单例
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取 Skill 注册中心单例"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _register_builtin_skills(_registry)
    return _registry


def _register_builtin_skills(registry: SkillRegistry) -> None:
    """注册所有内置 Skill"""
    from src.skills.hot_topic_poem.workflow import create_skill as create_hot_topic_skill

    registry.register(create_hot_topic_skill())
