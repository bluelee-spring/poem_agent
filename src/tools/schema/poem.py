"""诗千家 API 工具 Schema — 诗歌生成与参考数据查询"""

# ============================================================
# 诗歌生成工具
# ============================================================
GENERATE_POEM_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_poem",
        "description": "调用诗千家 API 生成古典诗歌。根据指定的诗体、风格、情感、韵部等参数，生成一首或多首诗歌。",
        "parameters": {
            "type": "object",
            "properties": {
                "poem_type": {
                    "type": "string",
                    "enum": ["五言律诗", "七言律诗", "五言绝句", "七言绝句"],
                    "description": "诗体类型",
                },
                "theme": {
                    "type": "string",
                    "description": "创作主题，如'春日怀乡'、'科技兴国'",
                },
                "style": {
                    "type": "string",
                    "enum": ["清新", "沉郁", "豪放", "婉约", "典雅"],
                    "description": "诗歌风格",
                },
                "emotion": {
                    "type": "string",
                    "enum": ["赞美", "感慨", "思念", "伤感", "讽刺", "忧虑", "闲适", "激昂", "喜悦", "思考"],
                    "description": "情感倾向",
                },
                "rhyme": {
                    "type": "string",
                    "enum": ["平水", "词林", "中华"],
                    "description": "韵部体系",
                },
                "imagery": {
                    "type": "string",
                    "description": "意象关键词，如'明月、秋风、孤雁'",
                },
                "allusions": {
                    "type": "string",
                    "description": "用典说明，如'化用陶渊明归去来兮辞'",
                },
                "title": {
                    "type": "string",
                    "description": "诗歌题目",
                },
                "count": {
                    "type": "integer",
                    "description": "生成诗歌数量，默认 1，最大 5",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 5,
                },
                "additional_requirements": {
                    "type": "string",
                    "description": "其他创作要求",
                },
            },
            "required": ["poem_type", "theme"],
        },
    },
}

# ============================================================
# 参考数据查询工具
# ============================================================
GET_REFERENCES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_references",
        "description": "获取诗千家平台支持的参考数据，包括可用的韵部列表、场景分类等。用于在规划阶段了解平台能力范围。",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["rhyme", "scene", "all"],
                    "description": "查询类型：rhyme=韵部树, scene=场景树, all=全部",
                    "default": "all",
                },
            },
        },
    },
}
