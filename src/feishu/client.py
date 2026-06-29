"""飞书 REST API 客户端 — Token 管理 + 消息 + Wiki + Bitable

v0.3 增强:
  - Wiki API: get_wiki_obj_token() 通过 wiki_token 获取 bitable app_token
  - Bitable API: write_poem_record() 写入多维表格记录
"""

import json
import os
import time
import httpx
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# Wiki / Bitable 配置
WIKI_TOKEN = os.getenv("FEISHU_WIKI_TOKEN", "OofGwwSuRiDblfksV9kc2XadnJc")
TABLE_ID = os.getenv("FEISHU_TABLE_ID", "tblSgghJkzr7Vz3A")
# cpolar 回调地址（如 "https://xxxx.cpolar.cn"），为空则自动检测
CPOLAR_URL = os.getenv("CPOLAR_URL", "")


@dataclass
class FeishuClient:
    """飞书 API 客户端（含 Wiki + Bitable）

    使用方式:
        client = FeishuClient()
        obj_token = await client.get_wiki_obj_token()
        await client.write_poem_record({"诗作": "...", ...})
    """

    app_id: str = FEISHU_APP_ID
    app_secret: str = FEISHU_APP_SECRET
    base_url: str = FEISHU_BASE_URL

    _token: str = ""
    _token_expires: float = 0.0
    _bitable_app_token: str = ""  # 缓存从 Wiki 获取的 obj_token

    # ============================================================
    # Token 管理
    # ============================================================
    async def _get_token(self) -> str:
        """获取 tenant_access_token（自动缓存）"""
        now = time.time()
        if self._token and now < self._token_expires - 60:
            return self._token

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        self._token = data["tenant_access_token"]
        self._token_expires = now + data.get("expire", 7200)
        return self._token

    async def _headers(self) -> dict:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ============================================================
    # 消息发送
    # ============================================================
    async def send_reply(self, message_id: str, text: str) -> dict:
        """回复飞书文本消息"""
        token = await self._get_token()
        body = {"content": json.dumps({"text": text}), "msg_type": "text"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/im/v1/messages/{message_id}/reply",
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_text(self, receive_id: str, text: str, id_type: str = "") -> dict:
        """发送文本消息（非回复场景）
        Args: receive_id=接收者ID, text=内容, id_type=open_id/chat_id/user_id
        """
        token = await self._get_token()
        body = {"receive_id": receive_id, "msg_type": "text",
                "content": json.dumps({"text": text})}
        if id_type:
            body["receive_id_type"] = id_type
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/im/v1/messages",
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    # ============================================================
    # Wiki API — 获取 Bitable 真实 app_token
    # ============================================================
    async def get_wiki_obj_token(self, wiki_token: str = "") -> str:
        """通过 Wiki 节点 token 获取多维表格的真实 app_token (obj_token)

        必须调用此接口拿 obj_token，不可直接用 wiki_token 作为 bitable app_token。

        Args:
            wiki_token: Wiki 节点 token，默认使用环境变量 FEISHU_WIKI_TOKEN

        Returns:
            Bitable 的 obj_token（即 app_token）
        """
        if self._bitable_app_token:
            return self._bitable_app_token

        token = wiki_token or WIKI_TOKEN
        if not token:
            raise ValueError("未设置 Wiki token（环境变量 FEISHU_WIKI_TOKEN）")

        headers = await self._headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/wiki/v2/spaces/get_node",
                params={"token": token},
                headers=headers,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Wiki API 失败 (HTTP {resp.status_code}): {resp.text[:300]}\n"
                    f"请确认：\n"
                    f"  1. 飞书应用的权限已开通: wiki:wiki:readonly\n"
                    f"  2. Wiki token 正确: {token}"
                )
            data = resp.json()
            node = data.get("data", {}).get("node", {})
            obj_type = node.get("obj_type", "")
            obj_token = node.get("obj_token", "")
            title = node.get("title", "")

            logger.info(f"[Wiki] obj_type={obj_type}, title={title}, obj_token={obj_token[:20]}...")

            if not obj_token:
                raise RuntimeError(
                    f"未获取到 obj_token。obj_type={obj_type}, 完整响应: {resp.text[:500]}\n"
                    f"请确认 Wiki 节点内嵌了多维表格（Bitable）。"
                )

            self._bitable_app_token = obj_token
            return obj_token

    # ============================================================
    # Bitable API — 写入多维表格记录
    # ============================================================
    async def write_poem_record(
        self,
        fields: dict[str, str],
        table_id: str = "",
        app_token: str = "",
    ) -> dict:
        """向多维表格写入一条诗歌记录

        Args:
            fields: 字段映射，如 {"诗作": "...", "创作日期": "2026-06-29"}
            table_id: 表 ID，默认环境变量
            app_token: Bitable app_token，默认从 Wiki 自动获取

        Returns:
            API 响应 JSON
        """
        _app_token = app_token or await self.get_wiki_obj_token()
        _table_id = table_id or TABLE_ID

        headers = await self._headers()
        body = {"fields": fields}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/bitable/v1/apps/{_app_token}/tables/{_table_id}/records",
                json=body,
                headers=headers,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Bitable 写入失败 (HTTP {resp.status_code}): {resp.text[:300]}\n"
                    f"请确认：\n"
                    f"  1. 飞书应用权限: bitable:app\n"
                    f"  2. 表字段名称与多维表格完全一致\n"
                    f"  3. app_token={_app_token[:20]}..."
                )
            return resp.json()

    async def send_to_chat(self, chat_id: str, text: str) -> dict:
        """向群聊发送文本消息（receive_id_type 作为查询参数）"""
        token = await self._get_token()
        body = {"receive_id": chat_id, "msg_type": "text",
                "content": json.dumps({"text": text})}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/im/v1/messages?receive_id_type=chat_id",
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def batch_write_records(
        self,
        records: list[dict[str, str]],
        table_id: str = "",
        app_token: str = "",
    ) -> int:
        """批量写入多条记录，返回成功数"""
        success = 0
        for fields in records:
            try:
                await self.write_poem_record(fields, table_id, app_token)
                success += 1
            except Exception as e:
                logger.error(f"批量写入失败: {e}")
        return success

    # ============================================================
    # cpolar 辅助
    # ============================================================
    @staticmethod
    async def detect_cpolar_url() -> str:
        """检测 cpolar 内网穿透公网地址"""
        if CPOLAR_URL:
            return CPOLAR_URL
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                resp = await c.get("http://127.0.0.1:4040/api/tunnels")
                if resp.status_code == 200:
                    tunnels = resp.json().get("tunnels", [])
                    for t in tunnels:
                        if t.get("proto") == "https":
                            return t.get("public_url", "")
        except Exception:
            pass
        return ""