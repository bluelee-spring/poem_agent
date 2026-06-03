"""诗千家 API Handler — 工具执行层

将 PoemsAPI 和 ReferenceAPI 封装为工具 handler 函数。
每个 handler 接收 arguments dict，返回结果 dict。
"""

from typing import Any
from src.api.poems import PoemsAPI, PoemParams
from src.api.reference import ReferenceAPI


async def handle_generate_poem(arguments: dict[str, Any]) -> dict[str, Any]:
    """生成诗歌

    Args:
        arguments: 包含 poem_type, theme, style, emotion, rhyme 等参数

    Returns:
        {"poems": [{"title": "...", "content": "...", ...}, ...]}
    """
    count = arguments.get("count", 1)
    count = max(1, min(count, 5))  # 限制 1-5

    params = PoemParams(
        poem_type=arguments.get("poem_type", ""),
        theme=arguments.get("theme", ""),
        style=arguments.get("style", ""),
        emotion=arguments.get("emotion", ""),
        rhyme=arguments.get("rhyme", ""),
        imagery=arguments.get("imagery", ""),
        allusions=arguments.get("allusions", ""),
        title=arguments.get("title", ""),
        additional_requirements=arguments.get("additional_requirements", ""),
    )

    api = PoemsAPI()
    poems = []

    for i in range(count):
        # 多首生成时微调参数避免完全重复
        if i > 0:
            params.extra = {"seed": i, "variant": i}

        try:
            batch = await api.generate_poem(params)
            poems.extend(batch)
        except RuntimeError as e:
            # 500 / 认证 / 网络错误直接抛出
            return {"success": False, "error": str(e)}
        except Exception as e:
            # 单首失败继续尝试
            continue

    if not poems:
        return {"success": False, "error": "API 未返回任何诗歌"}

    return {
        "success": True,
        "count": len(poems),
        "poems": [
            {
                "title": p.title or "(无题)",
                "content": p.content,
                "author_style": p.author_style,
            }
            for p in poems
        ],
    }


async def handle_get_references(arguments: dict[str, Any]) -> dict[str, Any]:
    """获取参考数据

    Args:
        arguments: {"type": "rhyme" | "scene" | "all"}

    Returns:
        参考数据字典
    """
    ref_type = arguments.get("type", "all")
    api = ReferenceAPI()

    result = {"success": True}

    if ref_type in ("rhyme", "all"):
        try:
            rhyme_names = await api.get_rhyme_names()
            result["rhyme_categories"] = rhyme_names[:30]  # 截取前 30 个
        except Exception as e:
            result["rhyme_error"] = str(e)

    if ref_type in ("scene", "all"):
        try:
            scene_tree = await api.get_scene_tree()
            # 只提取顶层场景名，减少 token
            if scene_tree:
                scenes = _extract_scene_names(scene_tree)
                result["scenes"] = scenes[:20]
        except Exception as e:
            result["scene_error"] = str(e)

    return result


def _extract_scene_names(tree: dict, max_depth: int = 2) -> list[str]:
    """从场景树中提取场景名称列表"""
    names = []

    def walk(node, depth=0):
        if depth > max_depth:
            return
        name = node.get("name") or node.get("label") or ""
        if name:
            names.append(name)
        children = node.get("children", [])
        for child in children:
            walk(child, depth + 1)

    # tree 可能是 {"tree": [...]} 或直接是列表
    items = tree.get("tree") or tree.get("data") or tree
    if isinstance(items, list):
        for item in items:
            walk(item)
    elif isinstance(items, dict):
        walk(items)

    return names


# 注册函数：将 handler 注册到 ToolRegistry
def register_handlers(registry: "ToolRegistry"):
    """将 poem_api handler 注册到工具注册中心"""
    from src.tools.schema.poem import GENERATE_POEM_SCHEMA, GET_REFERENCES_SCHEMA

    registry.register(GENERATE_POEM_SCHEMA, handle_generate_poem)
    registry.register(GET_REFERENCES_SCHEMA, handle_get_references)
