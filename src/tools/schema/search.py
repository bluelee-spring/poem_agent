"""搜索工具 Schema — 热搜采集 + 网页搜索"""

# ============================================================
# 热搜话题采集
# ============================================================
SEARCH_HOT_TOPICS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_hot_topics",
        "description": (
            "获取当前微博和百度的热搜话题列表。"
            "每个话题包含：排名、标题、热度值、来源、新闻摘要(summary)、链接(url)。"
            "百度热搜自带新闻摘要（100-200字），可用于了解热点事件的来龙去脉。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回的热搜数量上限，默认 20。建议设 25-30 确保覆盖面",
                    "default": 20,
                    "minimum": 5,
                    "maximum": 50,
                },
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["weibo", "baidu"],
                    },
                    "description": "指定搜索来源，默认全部（weibo + baidu）",
                },
            },
        },
    },
}

# ============================================================
# 网页搜索（了解热点详情）
# ============================================================
WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索网页获取某个话题的详细信息。"
            "用于深入了解热点事件的背景、来龙去脉。"
            "注意：DuckDuckGo 在国内经常不可用，此时请直接基于热搜摘要(summary)和已有知识分析，不要重试。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如'宜宾地震 5.5级'",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
}
