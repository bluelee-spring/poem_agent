"""热点采集模块 - 从各大平台获取热门话题"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HotTopic:
    """热点话题"""
    title: str
    rank: int = 0
    heat: str = ""
    source: str = ""
    url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class HotTopicCollector:
    """热点采集器基类"""

    async def fetch_weibo_hot(self, limit: int = 20) -> list[HotTopic]:
        """获取微博热搜（需要解析网页）"""
        import httpx

        topics = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 微博热搜 API（公开接口）
                resp = await client.get(
                    "https://weibo.com/ajax/side/hotSearch",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", {}).get("realtime", [])
                    for i, item in enumerate(items[:limit]):
                        word = item.get("word", "") or item.get("note", "")
                        if word:
                            topics.append(HotTopic(
                                title=word.strip(),
                                rank=i + 1,
                                heat=str(item.get("num", "")),
                                source="微博热搜",
                            ))
        except Exception:
            pass

        return topics

    async def fetch_baidu_hot(self, limit: int = 20) -> list[HotTopic]:
        """获取百度热搜"""
        import httpx

        topics = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://top.baidu.com/board?tab=realtime",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.status_code == 200:
                    # 简单解析（MVP 阶段用 BS4 或正则）
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    items = soup.select(".category-wrap_iQLoo")[:limit]
                    for i, item in enumerate(items):
                        title_el = item.select_one(".c-single-text-ellipsis")
                        if title_el:
                            topics.append(HotTopic(
                                title=title_el.text.strip(),
                                rank=i + 1,
                                source="百度热搜",
                            ))
        except Exception:
            pass

        return topics

    async def collect_all(self, limit: int = 20) -> list[HotTopic]:
        """汇总所有平台热点"""
        all_topics = []

        weibo = await self.fetch_weibo_hot(limit)
        all_topics.extend(weibo)

        baidu = await self.fetch_baidu_hot(limit)
        all_topics.extend(baidu)

        # 按排名排序，去重
        seen = set()
        unique = []
        for t in sorted(all_topics, key=lambda x: x.rank):
            if t.title not in seen:
                seen.add(t.title)
                unique.append(t)

        return unique[:limit]
