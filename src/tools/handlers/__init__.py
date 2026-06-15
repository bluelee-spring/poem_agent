"""Tool Handler 包 — 工具实现与注册入口"""

from src.tools.handlers.poem_api import register_handlers as register_poem_handlers
from src.tools.handlers.search import register_handlers as register_search_handlers
from src.tools.handlers.storage import register_handlers as register_storage_handlers
from src.tools.handlers.metrics import register_handlers as register_metrics_handlers
from src.tools.handlers.skill_loader import register_handlers as register_skill_handlers

__all__ = [
    "register_poem_handlers",
    "register_search_handlers",
    "register_storage_handlers",
    "register_metrics_handlers",
    "register_skill_handlers",
]
