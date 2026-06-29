"""飞书模块 — Bot + 定时任务 + 批量创作 + Bitable 写入

模块:
  client.py       — 飞书 REST API 客户端（消息 + Wiki + Bitable）
  bot.py          — WebSocket/Webhook 双模式 + 定时任务集成
  scheduler.py    — 基于 asyncio 的定时调度器
  batch_creator.py — 批量诗歌创作流程（搜热点→创作→写入多维表格）
"""

from src.feishu.bot import FeishuBot
from src.feishu.client import FeishuClient
from src.feishu.batch_creator import BatchPoemCreator, BatchResult, PoemRecord
from src.feishu.scheduler import AsyncScheduler

__all__ = [
    "FeishuBot",
    "FeishuClient",
    "BatchPoemCreator",
    "BatchResult",
    "PoemRecord",
    "AsyncScheduler",
]
