"""统一的 HTTP 客户端 - 自动注入 Bearer token"""

import httpx
from src.config import config


class PoemClient:
    """诗千家 API 客户端，管理 HTTP 会话和认证"""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or config.POEM_BASE_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def token(self) -> str:
        return config.POEM_ACCESS_TOKEN

    async def _get_client(self) -> httpx.AsyncClient:
        """懒加载 HTTP 客户端"""
        if self._client is None:
            headers = {
                "Accept": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, **kwargs) -> httpx.Response:
        client = await self._get_client()
        return await client.get(path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        client = await self._get_client()
        return await client.post(path, **kwargs)

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        client = await self._get_client()
        return await client.request(method, path, **kwargs)


# 全局客户端单例
_client_instance: PoemClient | None = None


def get_client() -> PoemClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = PoemClient()
    return _client_instance


async def close_client():
    global _client_instance
    if _client_instance:
        await _client_instance.close()
        _client_instance = None
