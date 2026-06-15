"""存储 Handler — 创作历史保存与查询

所有 JSON 文件读写统一通过 memory 层的 PoemHistory / PreferenceManager，
消除 handler 内联重复的 JSON I/O 逻辑。
"""

from typing import Any
from src.memory.history import get_history
from src.memory.preference import get_preferences


async def handle_save_poem(arguments: dict[str, Any]) -> dict[str, Any]:
    """保存诗歌到历史记录，并更新用户偏好统计

    Args:
        arguments: 包含 title, content 及可选的 poem_type, style, emotion, topic, score, comment

    Returns:
        {"success": True, "id": "...", "total_records": N}
    """
    h = get_history()

    record = {
        "title": arguments.get("title", "(无题)"),
        "content": arguments.get("content", ""),
        "poem_type": arguments.get("poem_type", ""),
        "style": arguments.get("style", ""),
        "emotion": arguments.get("emotion", ""),
        "topic": arguments.get("topic", ""),
        "score": arguments.get("score"),
        "comment": arguments.get("comment", ""),
    }

    saved = h.add(record)

    # 更新用户偏好统计
    prefs = get_preferences()
    if arguments.get("poem_type"):
        prefs.update_stats("poem_type", arguments["poem_type"])
    if arguments.get("style"):
        prefs.update_stats("style", arguments["style"])

    return {"success": True, "id": saved["id"], "total_records": h.count()}


async def handle_get_history(arguments: dict[str, Any]) -> dict[str, Any]:
    """查询历史记录

    Args:
        arguments: {"limit": 10, "topic": "春", "min_score": 7.0}

    Returns:
        {"success": True, "count": N, "total": M, "records": [...]}
    """
    h = get_history()

    records = h.query(
        topic=arguments.get("topic"),
        min_score=arguments.get("min_score"),
        limit=arguments.get("limit", 10),
    )

    return {
        "success": True,
        "count": len(records),
        "total": h.count(),
        "records": records,
    }


def register_handlers(registry: "ToolRegistry"):
    """将存储 handler 注册到工具注册中心"""
    from src.tools.schema.storage import SAVE_POEM_SCHEMA, GET_HISTORY_SCHEMA

    registry.register(SAVE_POEM_SCHEMA, handle_save_poem)
    registry.register(GET_HISTORY_SCHEMA, handle_get_history)
