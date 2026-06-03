"""Memory 层 — 创作历史记录的封装

提供对 data/history.json 的高层读写接口。
底层存储由 tools/handlers/storage.py 处理。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import config


class PoemHistory:
    """诗歌创作历史管理器"""

    def __init__(self):
        self._path = config.data_dir / "history.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[dict]:
        """加载所有历史记录"""
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, records: list[dict]) -> None:
        """保存历史记录"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, record: dict) -> dict:
        """添加一条记录"""
        records = self.load()
        record["id"] = record.get("id") or f"poem_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(records)}"
        record["created_at"] = record.get("created_at") or datetime.now().isoformat()
        records.append(record)
        self.save(records)
        return record

    def query(
        self,
        topic: str | None = None,
        min_score: float | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """查询历史记录"""
        records = self.load()
        if topic:
            topic_lower = topic.lower()
            records = [
                r for r in records
                if topic_lower in r.get("topic", "").lower()
                or topic_lower in r.get("title", "").lower()
            ]
        if min_score is not None:
            records = [
                r for r in records
                if r.get("score") is not None and r["score"] >= min_score
            ]
        return list(reversed(records))[:limit]

    def latest(self, n: int = 5) -> list[dict]:
        """获取最近 n 条记录"""
        records = self.load()
        return list(reversed(records))[:n]

    def count(self) -> int:
        """总记录数"""
        return len(self.load())

    def clear(self) -> None:
        """清空历史"""
        self.save([])


# 全局单例
_history: Optional[PoemHistory] = None


def get_history() -> PoemHistory:
    """获取 PoemHistory 单例"""
    global _history
    if _history is None:
        _history = PoemHistory()
    return _history
