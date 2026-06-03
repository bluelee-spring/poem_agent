"""
首次认证辅助脚本。

用法:
  1. 先运行:    python scripts/capture_auth.py
  2. 复制打印的 URL 在浏览器打开，完成 PKU 登录
  3. 浏览器重定向后，从地址栏复制 token
  4. 再运行:    python scripts/capture_auth.py --save <token>
"""

import sys
import os
import asyncio
import httpx


BASE_URL = "https://poem.pkudh.org"


async def get_login_url():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        resp = await client.get("/oauth/login", params={"debug": True})
        resp.raise_for_status()
        data = resp.json()
        return data


async def check_token(token: str):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        resp = await client.get(
            "/oauth/check-login",
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code == 200, resp.json()


def save_token(token: str):
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    content = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

    import re
    if "POEM_ACCESS_TOKEN=" in content:
        content = re.sub(r"POEM_ACCESS_TOKEN=.*", f"POEM_ACCESS_TOKEN={token}", content)
    else:
        content += f"\nPOEM_ACCESS_TOKEN={token}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Token 已保存到 {env_path}")


async def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--save":
        token = sys.argv[2]
        ok, data = await check_token(token)
        if ok:
            save_token(token)
            print(f"用户信息: {data}")
        else:
            print(f"❌ Token 无效: {data}")
    else:
        result = await get_login_url()
        print("=" * 60)
        print("请在浏览器中打开以下链接并完成 PKU 统一认证：")
        print("=" * 60)
        print(result)
        print("=" * 60)
        print("\n认证完成后，运行以下命令保存 token：")
        print('  python scripts/capture_auth.py --save "<你的token>"')


if __name__ == "__main__":
    asyncio.run(main())
