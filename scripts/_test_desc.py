"""探测百度热搜摘要完整文本"""
import asyncio
import httpx
from bs4 import BeautifulSoup

async def probe():
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://top.baidu.com/board?tab=realtime",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        soup = BeautifulSoup(resp.text, "lxml")
        items = soup.select(".category-wrap_iQLoo")[:2]
        for i, item in enumerate(items):
            desc = item.select_one(".hot-desc_1m_jR")
            if desc:
                # 完整 HTML
                print(f"=== ITEM {i} hot-desc HTML ===")
                print(desc.prettify()[:2000])
                print()
                # 完整文本（不去掉 a 标签）
                print(f"=== ITEM {i} hot-desc TEXT ===")
                print(repr(desc.get_text()))
                print(f"长度: {len(desc.get_text())}")

asyncio.run(probe())
