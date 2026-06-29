"""搜索 Handler — 热搜采集 + 网页搜索

将原 collectors/hot_topics.py 的采集逻辑内联到 handler 层，
消除不必要的中间抽象层。统一入口为 fetch_hot_topics()。

v0.3 改进：
  - 百度热搜增加新闻摘要抓取（hot-desc），不再只有标题
  - 微博热搜增强反爬策略 + 优雅降级
  - HotTopic 增加 summary 字段
"""

from dataclasses import dataclass, field
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
    summary: str = ""  # 新闻摘要 / 背景描述（v0.3 新增）


# ============================================================
# 内部工具函数
# ============================================================

def _clean_text(text: str) -> str:
    """清理文本：去除多余空白和乱码"""
    import re
    # 去除零宽字符和不可见控制符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\ufeff]', '', text)
    # 合并多个空白为单个空格
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============================================================
# 热搜采集
# ============================================================

async def _fetch_weibo_hot(limit: int = 20) -> list[HotTopic]:
    """获取微博热搜

    微博 API 反爬策略多变，提供多重降级：
      1. 标准 API (weibo.com/ajax/side/hotSearch)
      2. 备用 API (tenapi 等第三方接口)
    """
    topics = []

    # 方案 1：标准微博 API
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://weibo.com/ajax/side/hotSearch",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://weibo.com/",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", {}).get("realtime", [])
                for i, item in enumerate(items[:limit]):
                    word = item.get("word", "") or item.get("note", "")
                    if word:
                        # 提取话题 ID，构造 URL
                        word_scheme = item.get("word_scheme", "") or item.get("topic", "")
                        url = f"https://s.weibo.com/weibo?q=%23{word}%23" if word else ""
                        topics.append(HotTopic(
                            title=_clean_text(word),
                            rank=i + 1,
                            heat=str(item.get("num", "") or item.get("raw_hot", "")),
                            source="微博热搜",
                            url=url,
                        ))
                if topics:
                    return topics
    except Exception:
        pass

    # 方案 2：备用接口（如果主 API 403）
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://tenapi.cn/v2/weibohot",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])[:limit]
                for i, item in enumerate(items):
                    title = item.get("name", "") or item.get("word", "")
                    if title:
                        topics.append(HotTopic(
                            title=_clean_text(title),
                            rank=i + 1,
                            heat=str(item.get("hot", "") or item.get("num", "")),
                            source="微博热搜",
                            url=item.get("url", ""),
                        ))
    except Exception:
        pass

    return topics


async def _fetch_baidu_hot(limit: int = 20) -> list[HotTopic]:
    """获取百度热搜（含新闻摘要）

    百度热搜页面每个条目包含：
      - .c-single-text-ellipsis  → 标题
      - .hot-desc_1m_jR          → 新闻摘要（100-200 字）
      - .hot-index_1Bl1a         → 热度指数
      - a.title_dIF3B[href]      → 搜索链接
    """
    topics = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://top.baidu.com/board?tab=realtime",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                items = soup.select(".category-wrap_iQLoo")[:limit]
                for i, item in enumerate(items):
                    # 标题
                    title_el = item.select_one(".c-single-text-ellipsis")
                    if not title_el:
                        continue
                    title = _clean_text(title_el.text)

                    # 热度指数
                    heat_el = item.select_one(".hot-index_1Bl1a")
                    heat = _clean_text(heat_el.text) if heat_el else ""

                    # 新闻摘要（v0.3 核心改进）
                    summary_el = item.select_one(".hot-desc_1m_jR")
                    summary = ""
                    if summary_el:
                        # 去掉内部的 <a> 标签（"查看更多>"等）
                        for a in summary_el.find_all("a"):
                            a.decompose()
                        summary = _clean_text(summary_el.text)
                        # 截断过长摘要
                        if len(summary) > 300:
                            summary = summary[:300] + "..."

                    # 链接
                    link_el = item.select_one("a.title_dIF3B")
                    url = ""
                    if link_el:
                        url = link_el.get("href", "")
                        if url and not url.startswith("http"):
                            url = "https://top.baidu.com" + url

                    topics.append(HotTopic(
                        title=title,
                        rank=i + 1,
                        heat=heat,
                        source="百度热搜",
                        url=url,
                        summary=summary,
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
        去重并排序后的 HotTopic 列表（含摘要信息）
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
    """获取热搜话题列表（含新闻摘要）"""
    limit = arguments.get("limit", 20)
    sources = arguments.get("sources") or ["weibo", "baidu"]

    topics = await fetch_hot_topics(limit=limit, sources=sources)

    # 结构化返回：每个话题包含标题、排名、热度、来源、摘要
    return {
        "success": True,
        "count": len(topics),
        "topics": [
            {
                "rank": t.rank,
                "title": t.title,
                "source": t.source,
                "heat": t.heat,
                "summary": t.summary,
                "url": t.url,
            }
            for t in topics
        ],
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
        "note": (
            "DuckDuckGo 不可用（国内网络限制）。"
            "热搜话题已有新闻摘要（summary字段），请基于摘要和已有知识推断背景，"
            "不要再次调用 web_search。"
        ),
        "results": [],
    }


def register_handlers(registry: "ToolRegistry"):
    """将搜索 handler 注册到工具注册中心"""
    from src.tools.schema.search import SEARCH_HOT_TOPICS_SCHEMA, WEB_SEARCH_SCHEMA
    registry.register(SEARCH_HOT_TOPICS_SCHEMA, handle_search_hot_topics)
    registry.register(WEB_SEARCH_SCHEMA, handle_web_search)
