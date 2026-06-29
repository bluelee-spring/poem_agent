"""测试微博热搜抓取（含备用接口）"""
import asyncio
from src.tools.handlers.search import _fetch_weibo_hot

async def test():
    topics = await _fetch_weibo_hot(5)
    if not topics:
        print("微博热搜: 未获取到数据（API 可能被反爬）")
    for t in topics:
        print(f"#{t.rank} [{t.heat}] {t.title}")
        print(f"  摘要: {t.summary[:150] if t.summary else '(无)'}")
        print(f"  链接: {t.url}")
        print()

asyncio.run(test())
