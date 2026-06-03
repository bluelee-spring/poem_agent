"""OAuth 认证模块 - 处理 PKU 统一认证流程

实际 API 响应格式 (GET /oauth/login?debug=true):
{
    "auth_url": "https://id.pkudh.net/oauth/authorize?...",
    "params": {"client_id": "...", "scope": "...", ...},
    "nonce": "..."
}
"""

from src.api.client import get_client
from src.config import config


class AuthManager:
    """管理诗千家的 OAuth 认证"""

    async def get_login_info(self, debug: bool = True) -> dict:
        """
        获取登录入口信息（完整 JSON 响应）。
        返回: {"auth_url": str, "params": dict, "nonce": str}
        """
        client = get_client()
        resp = await client.get("/oauth/login", params={"debug": debug})
        resp.raise_for_status()
        return resp.json()

    async def get_auth_url(self, debug: bool = True) -> str:
        """
        获取认证 URL 字符串。
        用户在浏览器中打开此 URL 完成 PKU 统一认证。
        """
        info = await self.get_login_info(debug)
        return info.get("auth_url", str(info))

    async def check_login(self) -> dict:
        """验证当前 token 是否有效，返回用户信息"""
        client = get_client()
        resp = await client.get("/oauth/check-login")
        if resp.status_code == 200:
            return resp.json()
        return {"authenticated": False, "detail": resp.text}

    async def verify_token(self) -> bool:
        """简单判断 token 是否有效"""
        client = get_client()
        resp = await client.get("/oauth/check-login")
        return resp.status_code == 200

    @staticmethod
    def save_token(token: str, env_path=None):
        """
        将 token 写入 .env 文件。

        Args:
            token: Bearer token 字符串
            env_path: 可选的自定义 .env 路径
        """
        import re
        from pathlib import Path

        if env_path is None:
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"

        env_path = Path(env_path)
        content = ""
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")

        if "POEM_ACCESS_TOKEN=" in content:
            content = re.sub(
                r"POEM_ACCESS_TOKEN=.*",
                f"POEM_ACCESS_TOKEN={token}",
                content,
            )
        else:
            content += f"\nPOEM_ACCESS_TOKEN={token}\n"

        env_path.write_text(content, encoding="utf-8")
        # 同步更新内存中的配置
        config.POEM_ACCESS_TOKEN = token
