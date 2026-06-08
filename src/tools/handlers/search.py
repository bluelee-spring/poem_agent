"""搜索 Handler — 热搜采集 + 网页搜索"""

from typing import Any
import httpx
from src.collectors.hot_topics import HotTopicCollector


async def handle_search_hot_topics(arguments: dict[str, Any]) -> dict[str, Any]:
    """获取热搜话题列表"""
    limit = arguments.get("limit", 20)
    sources = arguments.get("sources") or ["weibo", "baidu"]

    collector = HotTopicCollector()
    all_topics = []

    if "weibo" in sources:
        try:
            weibo = await collector.fetch_weibo_hot(limit)
            all_topics.extend(weibo)
        except Exception:
            pass

    if "baidu" in sources:
        try:
            baidu = await collector.fetch_baidu_hot(limit)
            all_topics.extend(baidu)
        except Exception:
            pass

    seen = set()
    unique = []
    for t in sorted(all_topics, key=lambda x: x.rank):
        if t.title not in seen:
            seen.add(t.title)
            unique.append(t)

    topics = unique[:limit]

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
    from src.tools.schema.search import SEARCH_HOT_TOPICS_SCHEMA, WEB_SEARCH_SCHEMA
    registry.register(SEARCH_HOT_TOPICS_SCHEMA, handle_search_hot_topics)
    registry.register(WEB_SEARCH_SCHEMA, handle_web_search)
