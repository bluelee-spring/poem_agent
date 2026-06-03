"""Tool Handler 包"""

from src.tools.handlers.poem_api import register_handlers as register_poem_handlers
from src.tools.handlers.search import register_handlers as register_search_handlers
from src.tools.handlers.storage import register_handlers as register_storage_handlers

__all__ = [
    "register_poem_handlers",
    "register_search_handlers",
    "register_storage_handlers",
]
