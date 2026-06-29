"""飞书 Bot — 双模式触发（定时自动 + 用户私聊）+ cpolar 适配

模式选择:
  --mode ws       WebSocket 长连接（本地测试，不需要公网）
  --mode webhook  HTTP Webhook（生产发布，配合 cpolar 内网穿透）
  --mode both     WebSocket + 定时任务（本地长期运行）

触发方式:
  1. 定时自动: 每日 8:00 执行批量创作 → 写入 Wiki 多维表格
  2. 用户私聊: 发送 "创作" / "写诗" / "批量" → 立即触发批量创作
  3. 用户私聊: 其他消息 → 走智能对话（PoemController）

配置 (.env):
  FEISHU_APP_ID, FEISHU_APP_SECRET        飞书应用凭证
  FEISHU_WIKI_TOKEN                        Wiki 节点 token
  FEISHU_TABLE_ID                          多维表格 table_id
  FEISHU_SCHEDULE_TIME=08:00              定时执行时间
  FEISHU_SCHEDULE_ENABLED=true            是否启用定时
  FEISHU_REQUIRE_MENTION=true            群聊是否需 @
  CPOLAR_URL=                              cpolar 公网地址（可选）
  FEISHU_PORT=8080                        HTTP 端口
"""

import hashlib
import json
import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from aiohttp import web

from src.agent.controller import PoemController, AgentResult
from src.feishu.client import FeishuClient, FEISHU_APP_ID, FEISHU_APP_SECRET

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


# ============================================================
# 配置
# ============================================================
FEISHU_PORT = int(os.getenv("FEISHU_PORT", "8080"))
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")
FEISHU_REQUIRE_MENTION = os.getenv("FEISHU_REQUIRE_MENTION", "true").lower() != "false"
FEISHU_FORWARD_CHAT_ID = os.getenv("FEISHU_FORWARD_CHAT_ID", "")  # 转发到工作群的 chat_id


# ============================================================
# SDK 事件处理器包装
# ============================================================
class _EventHandler:
    """SDK WebSocket 模式要求 event_handler 有 _do_without_validation 方法"""
    def __init__(self, callback):
        self._callback = callback

    def _do_without_validation(self, payload: bytes):
        try:
            data = json.loads(payload.decode("utf-8"))
            self._callback(data)
        except Exception:
            pass


# ============================================================
# 消息处理核心
# ============================================================
class _MessageProcessor:
    """解析飞书事件 → 路由指令 → 执行"""

    # 触发批量创作的关键词
    BATCH_KEYWORDS = ["创作", "写诗", "批量", "batch", "生成", "作诗"]

    def __init__(self, api: FeishuClient):
        self._api = api
        self._controllers: dict[str, PoemController] = {}

    def _get_controller(self, chat_id: str) -> PoemController:
        if chat_id not in self._controllers:
            self._controllers[chat_id] = PoemController()
        return self._controllers[chat_id]

    async def handle(self, message: dict, message_id: str) -> None:
        """处理一条消息事件"""
        chat_id = message.get("chat_id", "unknown")

        # 提取文本
        content_str = message.get("content", "{}")
        try:
            content_obj = json.loads(content_str)
        except (json.JSONDecodeError, TypeError):
            content_obj = {}
        text = content_obj.get("text", "").strip()

        # 去掉 @mention
        if text.startswith("@_"):
            parts = text.split(" ", 1)
            text = parts[1] if len(parts) > 1 else ""

        if not text:
            return

        # @Bot 控制（群聊场景）
        if FEISHU_REQUIRE_MENTION:
            mentions = message.get("mentions", [])
            chat_type = message.get("chat_type", "group")
            # 私聊不需要 @
            if chat_type != "p2p" and not mentions:
                return

        logger.info(f"[飞书] chat={chat_id} 收到: {text[:80]}")

        try:
            reply = await self._route(chat_id, text, message_id)
        except Exception as e:
            logger.error(f"[飞书] 路由处理异常: {e}", exc_info=True)
            reply = f"处理失败: {e}"

        if message_id and reply:
            try:
                await self._api.send_reply(message_id, text=reply)
                logger.info(f"[飞书] 已回复 chat={chat_id}")
            except Exception as e:
                logger.error(f"[飞书] 回复失败: {e}")

    async def _route(self, chat_id: str, text: str, message_id: str = "") -> str:
        """路由消息到不同处理器"""
        text_lower = text.strip().lower()

        # 指令: reset
        if text_lower == "reset":
            self._controllers.pop(chat_id, None)
            return "上下文已清空，开始新会话。"

        # 指令: 批量创作触发词
        if any(kw in text_lower for kw in self.BATCH_KEYWORDS):
            return await self._handle_batch_trigger(text, message_id)

        # 指令: 状态查询
        if text_lower in ("status", "状态", "help", "帮助"):
            return self._help_text()

        # 默认: 智能对话
        return await self._handle_chat(chat_id, text)

    async def _handle_batch_trigger(self, user_text: str, message_id: str = "") -> str:
        """用户触发批量创作"""
        logger.info("[飞书] 触发批量创作")

        # 先回复"处理中"，用真实的 message_id
        if message_id:
            try:
                await self._api.send_reply(message_id, text="收到，正在批量创作（采集热点→写诗→写入多维表格）...")
            except Exception as e:
                logger.warning(f"发送处理中消息失败: {e}")

        try:
            from src.feishu.batch_creator import BatchPoemCreator
            creator = BatchPoemCreator(self._api)
            result = await creator.run(target_count=20, min_topics=5, verbose=False)
            wiki_token = os.getenv("FEISHU_WIKI_TOKEN", "OofGwwSuRiDblfksV9kc2XadnJc")
            wiki_url = os.getenv("FEISHU_WIKI_URL", "")
            wiki_link = wiki_url if wiki_url else f"https://{wiki_token[:8]}.feishu.cn/wiki/{wiki_token}"
            summary = (
                f"📜 今日诗歌创作完成！\n"
                f"📊 总计: {result.total} 首\n"
                f"✅ 成功: {result.success} 首\n"
                f"❌ 失败: {result.failed} 首\n"
                f"\n📋 查看多维表格: {wiki_link}"
            )

            # 转发到工作群
            forward_chat = os.getenv("FEISHU_FORWARD_CHAT_ID", "")
            if forward_chat:
                try:
                    await self._api.send_to_chat(forward_chat, summary)
                    logger.info(f"[飞书] 已转发到工作群 {forward_chat}")
                except Exception as e:
                    logger.warning(f"[飞书] 转发失败: {e}")

            return summary
        except Exception as e:
            logger.error(f"批量创作失败: {e}")
            return f"批量创作失败: {e}\n请检查日志。"

    async def _handle_chat(self, chat_id: str, text: str) -> str:
        """走 PoemController 智能对话"""
        ctrl = self._get_controller(chat_id)
        continue_session = bool(ctrl._messages)
        result: AgentResult = await ctrl.run(
            text, continue_session=continue_session, verbose=False,
        )
        if result.success:
            return result.output or "执行完成。"
        return f"执行失败: {result.error}"

    @staticmethod
    def _help_text() -> str:
        return (
            '\U0001f4d6 **诗千家智能体** 使用指南:\n'
            '- 发送 **创作** / **写诗** / **批量** → 立即批量创作 20 首\n'
            '- 发送具体主题（如 \u201c写一首春天的诗\u201d）→ 单首创作\n'
            '- 发送 **状态** / **帮助** → 查看此帮助\n'
            '- 发送 **reset** → 清空会话上下文\n'
            '- 每日 8:00 自动执行批量创作\n'
        )


# ============================================================
# FeishuBot — 统一入口
# ============================================================
class FeishuBot:
    """飞书 Bot 服务（双模式 + 定时任务）

    使用方式:
        bot = FeishuBot()
        await bot.run(mode="ws")        # WebSocket 长连接
        await bot.run(mode="webhook")   # HTTP Webhook（配合 cpolar）
        await bot.run(mode="both")      # WebSocket + 定时任务
    """

    def __init__(self):
        self._api = FeishuClient()
        self._processor = _MessageProcessor(self._api)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._http_runner = None
        self._scheduler = None

    # ---- WebSocket 模式 ----
    async def _run_ws(self) -> None:
        from lark_oapi.ws.client import Client as WsClient

        self._loop = asyncio.get_running_loop()
        logger.info("飞书 Bot 启动（WebSocket 长连接模式）...")

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            def _run():
                import lark_oapi.ws.client as _ws_client
                ws_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(ws_loop)
                _ws_client.loop = ws_loop

                def on_event(data: dict):
                    event = data.get("event", data)
                    header = data.get("header", {})
                    if header.get("event_type") != "im.message.receive_v1":
                        return
                    message = event.get("message", {})
                    mid = message.get("message_id", "")
                    if message and mid:
                        asyncio.run_coroutine_threadsafe(
                            self._processor.handle(message, mid), self._loop
                        )

                ws = WsClient(
                    app_id=FEISHU_APP_ID,
                    app_secret=FEISHU_APP_SECRET,
                    event_handler=_EventHandler(on_event),
                )
                logger.info("WebSocket 已连接，等待事件...")
                ws.start()
                ws_loop.close()

            try:
                await loop.run_in_executor(executor, _run)
            except KeyboardInterrupt:
                logger.info("飞书 Bot 已停止。")

    # ---- HTTP Webhook 模式 ----
    async def _run_webhook(self) -> None:
        app = web.Application()

        @web.middleware
        async def _log_all(request, handler):
            import sys
            sys.stderr.write(f"[AIOHTTP] {request.method} {request.path}\n")
            sys.stderr.flush()
            return await handler(request)

        app.middlewares.append(_log_all)
        app.router.add_post("/feishu/event", self._handle_webhook)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", FEISHU_PORT)
        await site.start()
        self._http_runner = runner

        # 检测 cpolar 地址
        cpolar_url = await FeishuClient.detect_cpolar_url()
        tips = (
            f"\n  回调 URL: http://你的公网IP:{FEISHU_PORT}/feishu/event"
        )
        if cpolar_url:
            tips = f"\n  cpolar 地址: {cpolar_url}/feishu/event"
            tips += f"\n  本地端口: {FEISHU_PORT}"
        tips += f"\n  Verification Token: {FEISHU_VERIFICATION_TOKEN[:8] if FEISHU_VERIFICATION_TOKEN else '(未设置)'}..."
        logger.info(f"飞书 Bot 启动（HTTP Webhook 模式，端口 {FEISHU_PORT}）{tips}")
        logger.info("按 Ctrl+C 停止")

        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            await runner.cleanup()
            logger.info("飞书 Bot 已停止。")

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """处理飞书 HTTP 回调"""
        body = await request.read()

        # 解密
        plaintext = body
        if FEISHU_ENCRYPT_KEY:
            try:
                from lark_oapi.core.cipher import AESCipher
                enc = json.loads(body)
                if enc.get("encrypt"):
                    plaintext = AESCipher(FEISHU_ENCRYPT_KEY).decrypt(enc["encrypt"]).encode()
            except Exception:
                pass

        try:
            data = json.loads(plaintext)
        except json.JSONDecodeError:
            logger.error(f"[Webhook] JSON 解析失败，原始 body: {body[:300]}")
            return web.Response(status=400, text="invalid json")

        # URL 验证（兼容新旧两种飞书格式）
        # 旧格式: {"type": "url_verification", "challenge": "xxx"}
        # 新格式: {"schema": "2.0", "header": {"event_type": "url_verification"}, "challenge": "xxx"}
        challenge = data.get("challenge", "")
        if data.get("type") == "url_verification" or (
            data.get("header", {}).get("event_type") == "url_verification"
        ):
            logger.info(f"[Webhook] URL 验证请求，challenge={challenge[:20]}...")
            return web.json_response({"challenge": challenge})

        # 验证签名
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        signature = request.headers.get("X-Lark-Signature", "")
        if FEISHU_ENCRYPT_KEY and not self._verify_sign(timestamp, nonce, signature, body):
            return web.Response(status=401, text="signature verification failed")

        # 分发事件
        header = data.get("header", {})
        event_type = header.get("event_type", "")
        logger.info(f"[Webhook] 事件类型: {event_type}")
        if event_type == "im.message.receive_v1":
            event = data.get("event", {})
            message = event.get("message", {})
            message_id = message.get("message_id", "")
            if message and message_id:
                asyncio.ensure_future(self._processor.handle(message, message_id))

        return web.json_response({"code": 0})

    @staticmethod
    def _verify_sign(timestamp: str, nonce: str, signature: str, body: bytes) -> bool:
        if not timestamp or not nonce or not signature:
            return False
        raw = (timestamp + nonce + FEISHU_ENCRYPT_KEY).encode() + body
        return signature == hashlib.sha256(raw).hexdigest()

    # ---- 定时任务 ----
    async def _run_scheduler(self) -> None:
        """启动定时调度器"""
        from src.feishu.scheduler import AsyncScheduler, setup_schedule_jobs
        self._scheduler = AsyncScheduler()
        setup_schedule_jobs(self._scheduler)
        logger.info("定时调度器已启动")
        await self._scheduler.start()

    # ---- 统一入口 ----
    async def run(self, mode: str = "ws") -> None:
        """启动飞书 Bot

        Args:
            mode: ws / webhook / both (WebSocket + 定时任务)
        """
        if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
            logger.error("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，请在 .env 中设置")
            return

        # 验证 Wiki 连接
        try:
            obj_token = await self._api.get_wiki_obj_token()
            logger.info(f"[飞书] Bitable app_token: {obj_token[:20]}...")
        except Exception as e:
            logger.warning(f"[飞书] Wiki 连接失败（Bitable 写入将不可用）: {e}")

        if mode == "webhook":
            await self._run_webhook()
        elif mode == "both":
            # WebSocket + 定时任务并行
            await asyncio.gather(
                self._run_ws(),
                self._run_scheduler(),
            )
        else:
            await self._run_ws()
