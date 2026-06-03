"""搜索 Handler — 热搜采集 + 网页搜索"""

from typing import Any
from src.collectors.hot_topics import HotTopicCollector


async def handle_search_hot_topics(arguments: dict[str, Any]) -> dict[str, Any]:
    """获取热搜话题列表

    Args:
        arguments: {"limit": 20, "sources": ["weibo", "baidu"]}

    Returns:
        {"topics": [{"rank": 1, "title": "...", "heat": "...", "source": "..."}, ...]}
    """
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

    # 去重排序
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
        "topics": [
            {
                "rank": t.rank,
                "title": t.title,
                "heat": t.heat,
                "source": t.source,
            }
            for t in topics
        ],
    }


async def handle_web_search(arguments: dict[str, Any]) -> dict[str, Any]:
    """网页搜索 — 通过 DuckDuckGo 获取网页摘要

    Args:
        arguments: {"query": "搜索关键词", "limit": 5}

    Returns:
        {"results": [{"title": "...", "snippet": "...", "url": "..."}, ...]}
    """
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)

    if not query:
        return {"success": False, "error": "搜索关键词不能为空"}

    import httpx

    results = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 使用 DuckDuckGo Instant Answer API（无需 API Key）
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
                headers={"User-Agent": "PoemAgent/1.0"},
            )

            if resp.status_code == 200:
                data = resp.json()

                # Abstract 摘要
                abstract = data.get("AbstractText", "")
                abstract_url = data.get("AbstractURL", "")
                if abstract:
                    results.append({
                        "title": data.get("Heading", query),
                        "snippet": abstract[:300],
                        "url": abstract_url,
                    })

                # Related topics
                for topic in data.get("RelatedTopics", [])[:limit - len(results)]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                            "snippet": topic.get("Text", "")[:200],
                            "url": topic.get("FirstURL", ""),
                        })

    except Exception as e:
        # DuckDuckGo 失败不阻塞流程，返回空结果
        return {"success": True, "results": results, "note": f"搜索受限: {e}"}

    if not results:
        results.append({
            "title": query,
            "snippet": f"未找到 '{query}' 的详细搜索结果，建议基于已有知识创作。",
            "url": "",
        })

    return {"success": True, "count": len(results), "results": results}


def register_handlers(registry: "ToolRegistry"):
    """将搜索 handler 注册到工具注册中心"""
    from src.tools.schema.search import SEARCH_HOT_TOPICS_SCHEMA, WEB_SEARCH_SCHEMA

    registry.register(SEARCH_HOT_TOPICS_SCHEMA, handle_search_hot_topics)
    registry.register(WEB_SEARCH_SCHEMA, handle_web_search)
