"""存储 Handler — 创作历史保存与查询"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import config


def _get_history_path() -> Path:
    """获取 history.json 的路径"""
    return config.data_dir / "history.json"


def _load_history() -> list[dict]:
    """加载历史记录"""
    path = _get_history_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(records: list[dict]) -> None:
    """保存历史记录"""
    path = _get_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def handle_save_poem(arguments: dict[str, Any]) -> dict[str, Any]:
    """保存诗歌到历史记录

    Args:
        arguments: 包含 title, content 及可选的 poem_type, style, emotion, topic, score, comment

    Returns:
        {"success": True, "id": "..."}
    """
    records = _load_history()

    record = {
        "id": f"poem_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(records)}",
        "title": arguments.get("title", "(无题)"),
        "content": arguments.get("content", ""),
        "poem_type": arguments.get("poem_type", ""),
        "style": arguments.get("style", ""),
        "emotion": arguments.get("emotion", ""),
        "topic": arguments.get("topic", ""),
        "score": arguments.get("score"),
        "comment": arguments.get("comment", ""),
        "created_at": datetime.now().isoformat(),
    }

    records.append(record)
    _save_history(records)

    return {"success": True, "id": record["id"], "total_records": len(records)}


async def handle_get_history(arguments: dict[str, Any]) -> dict[str, Any]:
    """查询历史记录

    Args:
        arguments: {"limit": 10, "topic": "春", "min_score": 7.0}

    Returns:
        {"records": [...]}
    """
    records = _load_history()
    limit = arguments.get("limit", 10)
    topic = arguments.get("topic", "").lower()
    min_score = arguments.get("min_score")

    # 筛选
    filtered = records
    if topic:
        filtered = [
            r for r in filtered
            if topic in r.get("topic", "").lower() or topic in r.get("title", "").lower()
        ]
    if min_score is not None:
        filtered = [
            r for r in filtered
            if r.get("score") is not None and r["score"] >= min_score
        ]

    # 倒序取最新
    filtered = list(reversed(filtered))[:limit]

    return {"success": True, "count": len(filtered), "total": len(records), "records": filtered}


def register_handlers(registry: "ToolRegistry"):
    """将存储 handler 注册到工具注册中心"""
    from src.tools.schema.storage import SAVE_POEM_SCHEMA, GET_HISTORY_SCHEMA

    registry.register(SAVE_POEM_SCHEMA, handle_save_poem)
    registry.register(GET_HISTORY_SCHEMA, handle_get_history)
