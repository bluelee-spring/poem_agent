"""定时任务调度器 — 基于 asyncio 实现（零额外依赖）

支持两类任务:
  1. 每日定时批量创作（默认每天 8:00）
  2. 即时触发（用户私聊指令）

配置:
  .env: FEISHU_SCHEDULE_TIME=08:00  (UTC+8)
  .env: FEISHU_SCHEDULE_ENABLED=true
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 配置
SCHEDULE_TIME = os.getenv("FEISHU_SCHEDULE_TIME", "10:00")  # HH:MM
SCHEDULE_ENABLED = os.getenv("FEISHU_SCHEDULE_ENABLED", "true").lower() != "false"


class AsyncScheduler:
    """基于 asyncio 的轻量定时调度器

    使用方式:
        scheduler = AsyncScheduler()
        scheduler.add_cron("08:00", batch_create_poems)
        scheduler.add_interval(3600, heartbeat)        # 每小时
        await scheduler.start()
    """

    def __init__(self):
        self._tasks: list[asyncio.Task] = []
        self._running = False

    def add_cron(self, time_str: str, callback, *args, **kwargs):
        """添加每日定时任务（如 "08:00" 表示每天 8:00 执行）

        Args:
            time_str: UTC+8 时间，格式 "HH:MM"
            callback: 异步回调函数
        """
        async def _cron_loop():
            parts = time_str.split(":")
            target_hour = int(parts[0])
            target_minute = int(parts[1]) if len(parts) > 1 else 0

            logger.info(f"[调度] 每日 {time_str} 定时任务已注册")
            while self._running:
                now = datetime.now()
                target_today = now.replace(
                    hour=target_hour, minute=target_minute, second=0, microsecond=0
                )
                if now >= target_today:
                    target_today += timedelta(days=1)
                wait_seconds = (target_today - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                if not self._running:
                    break
                try:
                    logger.info(f"[调度] 执行定时任务: {time_str}")
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"[调度] 任务失败: {e}")

        task = asyncio.ensure_future(_cron_loop())
        self._tasks.append(task)
        return task

    def add_interval(self, seconds: float, callback, *args, **kwargs):
        """添加间隔任务"""
        async def _interval_loop():
            logger.info(f"[调度] 每 {seconds}s 间隔任务已注册")
            while self._running:
                await asyncio.sleep(seconds)
                if not self._running:
                    break
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"[调度] 间隔任务失败: {e}")

        task = asyncio.ensure_future(_interval_loop())
        self._tasks.append(task)
        return task

    async def start(self):
        """启动所有定时任务（永不返回，直到 cancel）"""
        self._running = True
        logger.info(f"[调度] 启动完成，{len(self._tasks)} 个任务")
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def cancel(self):
        """取消所有定时任务"""
        self._running = False
        for t in self._tasks:
            t.cancel()


# ============================================================
# 预置任务工厂
# ============================================================
async def _batch_poem_job():
    """每日定时批量创作任务"""
    import os
    from src.feishu.client import FeishuClient
    from src.feishu.batch_creator import BatchPoemCreator

    feishu = FeishuClient()
    creator = BatchPoemCreator(feishu)
    logger.info("[定时任务] 开始批量创作...")
    result = await creator.run(target_count=20, min_topics=5, verbose=True)
    logger.info(f"[定时任务] 完成: {result.success}/{result.total} 写入成功")

    # 转发到工作群
    forward_chat = os.getenv("FEISHU_FORWARD_CHAT_ID", "")
    if forward_chat:
        try:
            wiki_token = os.getenv("FEISHU_WIKI_TOKEN", "OofGwwSuRiDblfksV9kc2XadnJc")
            wiki_url = os.getenv("FEISHU_WIKI_URL", "")
            wiki_link = wiki_url if wiki_url else f"https://{wiki_token[:8]}.feishu.cn/wiki/{wiki_token}"
            summary = (
                f"📜 今日诗歌创作完成！\n"
                f"📊 总计: {result.total} 首 | ✅ 成功: {result.success} 首 | ❌ 失败: {result.failed} 首\n"
                f"\n📋 查看多维表格: {wiki_link}"
            )
            await feishu.send_to_chat(forward_chat, summary)
            logger.info(f"[定时任务] 已转发到工作群 {forward_chat}")
        except Exception as e:
            logger.warning(f"[定时任务] 转发失败: {e}")


def setup_schedule_jobs(scheduler: AsyncScheduler):
    """注册预置定时任务"""
    if SCHEDULE_ENABLED:
        scheduler.add_cron(SCHEDULE_TIME, _batch_poem_job)
    else:
        logger.info("[调度] 定时任务已禁用 (FEISHU_SCHEDULE_ENABLED=false)")
