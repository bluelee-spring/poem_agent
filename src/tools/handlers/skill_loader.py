"""use_skill Handler — 按需加载 Skill 的元工具

此 handler 返回简单确认信息。
实际的 Skill 加载逻辑（切换 prompt、过滤 tools）由 Controller 在执行后检测处理。
"""

from typing import Any
from src.skills.registry import get_skill_registry


async def handle_use_skill(arguments: dict[str, Any]) -> dict[str, Any]:
    """处理 use_skill 调用

    返回 skill 是否存在的确认信息。
    Controller 在收到此结果后会：
      1. 加载 Skill 的 system_prompt 并注入到对话
      2. 将可用工具集切换为 Skill 限定的子集
      3. 运行 Skill.setup（如果存在）
    """
    skill_name = arguments.get("name", "")
    registry = get_skill_registry()
    skill = registry.get(skill_name)

    if skill is None:
        available = registry.list()
        return {
            "success": False,
            "error": f"技能 '{skill_name}' 不存在。可用技能: {available}",
        }

    return {
        "success": True,
        "skill_name": skill_name,
        "skill_description": skill.description,
        "note": f"技能 '{skill_name}' 已加载，后续对话将使用该技能的专用工作流和工具集。",
    }


def register_handlers(registry: "ToolRegistry"):
    """注册 use_skill handler"""
    from src.tools.schema.skill import USE_SKILL_SCHEMA
    registry.register(USE_SKILL_SCHEMA, handle_use_skill)
