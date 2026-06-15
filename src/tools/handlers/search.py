"""搜索 Handler — 热搜采集 + 网页搜索

将原 collectors/hot_topics.py 的采集逻辑内联到 handler 层，
消除不必要的中间抽象层。统一入口为 fetch_hot_topics()。
"""

from dataclasses import dataclass
from typing import Any
import httpx
from bs4 import BeautifulSoup


# ============================================================
# 数据模型
# ============================================================

@dataclass
class HotTopic:
    """热点话题"""
    title: str
    rank: int = 0
    heat: str = ""
    source: str = ""
    url: str = ""


# ============================================================
# 热搜采集（原 collectors/hot_topics.py）
# ============================================================

async def _fetch_weibo_hot(limit: int = 20) -> list[HotTopic]:
    """获取微博热搜"""
    topics = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
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


async def _fetch_baidu_hot(limit: int = 20) -> list[HotTopic]:
    """获取百度热搜"""
    topics = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://top.baidu.com/board?tab=realtime",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
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


async def fetch_hot_topics(
    limit: int = 20,
    sources: list[str] | None = None,
) -> list[HotTopic]:
    """统一的公开入口：从多个来源采集热点，去重排序

    Args:
        limit: 返回数量上限
        sources: 采集来源列表，默认 ["weibo", "baidu"]

    Returns:
        去重并排序后的 HotTopic 列表
    """
    if sources is None:
        sources = ["weibo", "baidu"]

    all_topics = []

    if "weibo" in sources:
        all_topics.extend(await _fetch_weibo_hot(limit))
    if "baidu" in sources:
        all_topics.extend(await _fetch_baidu_hot(limit))

    seen = set()
    unique = []
    for t in sorted(all_topics, key=lambda x: x.rank):
        if t.title not in seen:
            seen.add(t.title)
            unique.append(t)

    return unique[:limit]


# ============================================================
# Tool Handler 函数
# ============================================================

async def handle_search_hot_topics(arguments: dict[str, Any]) -> dict[str, Any]:
    """获取热搜话题列表"""
    limit = arguments.get("limit", 20)
    sources = arguments.get("sources") or ["weibo", "baidu"]

    topics = await fetch_hot_topics(limit=limit, sources=sources)

    return {
        "success": True,
        "count": len(topics),
        "topics": [f"[{t.source}]#{t.rank} {t.title}" for t in topics],
    }


async def handle_web_search(arguments: dict[str, Any]) -> dict[str, Any]:
    """网页搜索。

    DuckDuckGo 在国内经常不通，失败时返回明确降级提示，
    LLM 应直接基于已有知识继续，不要重试。
    """
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)

    if not query:
        return {"success": False, "error": "搜索关键词不能为空"}

    results = []

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": "PoemAgent/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                if abstract:
                    results.append({
                        "title": data.get("Heading", query),
                        "snippet": abstract[:300],
                        "url": data.get("AbstractURL", ""),
                    })
                for topic in data.get("RelatedTopics", [])[:limit - len(results)]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                            "snippet": topic.get("Text", "")[:200],
                            "url": topic.get("FirstURL", ""),
                        })
    except httpx.TimeoutException:
        pass
    except Exception:
        pass

    if results:
        return {"success": True, "count": len(results), "results": results}

    return {
        "success": True,
        "search_available": False,
        "note": "DuckDuckGo 不可用（国内网络限制）。请直接基于热搜标题和已有知识推断背景，不要再次调用 web_search。",
        "results": [],
    }


def register_handlers(registry: "ToolRegistry"):
    """将搜索 handler 注册到工具注册中心"""
    from src.tools.schema.search import SEARCH_HOT_TOPICS_SCHEMA, WEB_SEARCH_SCHEMA
    registry.register(SEARCH_HOT_TOPICS_SCHEMA, handle_search_hot_topics)
    registry.register(WEB_SEARCH_SCHEMA, handle_web_search)
