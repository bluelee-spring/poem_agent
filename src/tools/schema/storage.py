"""存储工具 Schema — 创作历史保存与查询"""

# ============================================================
# 保存诗歌记录
# ============================================================
SAVE_POEM_SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_poem",
        "description": "将创作完成的诗歌保存到本地历史记录。包含诗歌内容、评分、评语、创作参数等。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "诗歌题目",
                },
                "content": {
                    "type": "string",
                    "description": "诗歌正文内容",
                },
                "poem_type": {
                    "type": "string",
                    "description": "诗体",
                },
                "style": {
                    "type": "string",
                    "description": "风格",
                },
                "emotion": {
                    "type": "string",
                    "description": "情感",
                },
                "topic": {
                    "type": "string",
                    "description": "创作主题/灵感来源",
                },
                "score": {
                    "type": "number",
                    "description": "综合评分 (1-10)",
                    "minimum": 0,
                    "maximum": 10,
                },
                "comment": {
                    "type": "string",
                    "description": "评语",
                },
            },
            "required": ["title", "content"],
        },
    },
}

# ============================================================
# 查询历史记录
# ============================================================
GET_HISTORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_history",
        "description": "查询之前创作的诗歌历史记录。可以按主题、评分范围等筛选。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认 10",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "topic": {
                    "type": "string",
                    "description": "按主题筛选（模糊匹配）",
                },
                "min_score": {
                    "type": "number",
                    "description": "最低评分筛选",
                },
            },
        },
    },
}
