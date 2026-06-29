"""测试百度热搜摘要抓取"""
import asyncio
from src.tools.handlers.search import _fetch_baidu_hot

async def test():
    topics = await _fetch_baidu_hot(5)
    for t in topics:
        print(f"#{t.rank} [{t.heat}] {t.title}")
        print(f"  摘要({len(t.summary)}字): {t.summary[:150]}")
        print(f"  链接: {t.url}")
        print()

asyncio.run(test())
