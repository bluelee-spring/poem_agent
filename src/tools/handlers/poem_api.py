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
            rhyme_tree = await api.get_rhyme_tree()
            # 提取韵部树摘要：每层最多展示一个节点的children以控制长度
            result["rhyme_tree"] = _summarize_rhyme_tree(rhyme_tree, max_top_nodes=15, max_child_nodes=8)
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


def _summarize_rhyme_tree(tree: list, max_top_nodes: int = 15, max_child_nodes: int = 8) -> list[dict]:
    """将韵部树摘要为 LLM 可读的结构

    保留顶层节点（如上平声、下平声等）和其子韵部名，
    控制每个节点的 children 数量避免 token 爆炸。
    """
    summary = []
    for node in tree[:max_top_nodes]:
        item = {
            "category": node.name,           # 如"上平声"
            "description": node.description or "",
        }
        children = node.children[:max_child_nodes]
        item["rhymes"] = [
            {"name": c.name, "desc": c.description or "", "chars": (c.characters or "")[:30]}
            for c in children
        ]
        if len(node.children) > max_child_nodes:
            item["truncated"] = f"（共{len(node.children)}个，已截取前{max_child_nodes}个）"
        summary.append(item)
    return summary


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
