"""use_skill 工具 Schema — 按需加载 Skill 的元工具"""

USE_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "use_skill",
        "description": (
            "按需加载一个技能（Skill）的完整工作流指令。"
            "当用户意图匹配某个技能时调用此工具，加载后你将获得该技能的详细工作流指导和专用工具集。"
            "注意：use_skill 只能调用一次，且调用后当前可用的工具集会变化。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "要加载的技能名称。可用技能列表见 System Prompt 中的「可用技能」。",
                },
            },
            "required": ["name"],
        },
    },
}
