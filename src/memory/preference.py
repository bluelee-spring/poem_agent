"""用户偏好管理 — 记录用户对诗体、风格等的偏好"""

import json
from pathlib import Path
from typing import Optional

from src.config import config


class PreferenceManager:
    """用户偏好管理器

    存储在 data/preference.json。
    """

    def __init__(self):
        self._path = config.data_dir / "preference.json"

    def load(self) -> dict:
        """加载偏好"""
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, prefs: dict) -> None:
        """保存偏好"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(prefs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str, default=None):
        """获取单个偏好"""
        return self.load().get(key, default)

    def set(self, key: str, value) -> None:
        """设置偏好"""
        prefs = self.load()
        prefs[key] = value
        self.save(prefs)

    def update_stats(self, field: str, value: str) -> None:
        """更新使用统计（如最常用的诗体、风格等）"""
        prefs = self.load()
        stats = prefs.get("stats", {})
        field_stats = stats.get(field, {})
        field_stats[value] = field_stats.get(value, 0) + 1
        stats[field] = field_stats
        prefs["stats"] = stats
        self.save(prefs)

    def top_preferences(self, field: str, n: int = 3) -> list[str]:
        """获取最常用的偏好项"""
        prefs = self.load()
        stats = prefs.get("stats", {}).get(field, {})
        sorted_items = sorted(stats.items(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_items[:n]]


# 全局单例
_prefs: Optional[PreferenceManager] = None


def get_preferences() -> PreferenceManager:
    """获取 PreferenceManager 单例"""
    global _prefs
    if _prefs is None:
        _prefs = PreferenceManager()
    return _prefs
