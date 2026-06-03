"""参考数据 API - 获取韵部树、场景树、题材、风格等可选值

已验证的 API:
- GET /rhymes/tree          → {"tree": [...]}    公开(无需认证)
- GET /scenes/tree          → 404 (路径待确认)
- 其他路径待后续探索
"""

from dataclasses import dataclass, field
from typing import Any
from src.api.client import get_client


@dataclass
class RhymeCategory:
    """韵部类别"""
    id: str = ""
    name: str = ""
    description: str = ""
    characters: str = ""
    notes: str = ""
    level: int = 0
    children: list["RhymeCategory"] = field(default_factory=list)


@dataclass
class ReferenceData:
    """诗千家平台支持的参考数据"""
    rhyme_categories: list[RhymeCategory] = field(default_factory=list)
    rhyme_names: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    scene_tree: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class ReferenceAPI:
    """获取诗千家的参考数据（题材/体裁/风格/韵部等）"""

    async def get_rhyme_tree(self) -> list[RhymeCategory]:
        """
        获取韵部树（已验证: GET /rhymes/tree，无需认证）。
        返回平水韵的完整层级结构。
        """
        client = get_client()
        resp = await client.get("/rhymes/tree")
        if resp.status_code == 200:
            data = resp.json()
            tree = data.get("tree", [])
            return self._parse_rhyme_nodes(tree)
        return []

    async def get_rhyme_names(self) -> list[str]:
        """获取韵部名称列表（扁平化）"""
        tree = await self.get_rhyme_tree()
        names = []
        for node in tree:
            names.append(node.name)
            for child in node.children:
                names.append(f"{node.name} - {child.name}")
        return names

    async def get_scene_tree(self) -> dict:
        """获取场景树（路径待确认，目前已知 /scenes/tree 返回 404）"""
        client = get_client()
        # 尝试可能的路径
        for path in ["/scenes/tree", "/scene/tree", "/scenes"]:
            resp = await client.get(path)
            if resp.status_code == 200:
                return resp.json()
        return {}

    async def get_all_references(self) -> ReferenceData:
        """一次性获取所有可用的参考数据"""
        ref = ReferenceData()

        # 韵部树（已验证可用）
        try:
            ref.rhyme_categories = await self.get_rhyme_tree()
            for node in ref.rhyme_categories:
                ref.rhyme_names.append(node.name)
                for child in node.children:
                    ref.rhyme_names.append(f"{node.name} - {child.name}")
        except Exception as e:
            print(f"[warn] 获取韵部失败: {e}")

        # 场景树
        try:
            ref.scene_tree = await self.get_scene_tree()
        except Exception:
            pass

        # 题材/体裁/风格（尝试各种可能路径）
        for path, key in [
            ("/config/topics", "topics"),
            ("/config/genres", "genres"),
            ("/config/styles", "styles"),
            ("/meta/topics", "topics"),
            ("/meta/genres", "genres"),
            ("/meta/styles", "styles"),
            ("/topics", "topics"),
            ("/genres", "genres"),
            ("/styles", "styles"),
        ]:
            try:
                resp = await client.get(path)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get(key) or data.get("data") or []
                    if isinstance(items, list) and items:
                        if key == "topics":
                            ref.topics = items
                        elif key == "genres":
                            ref.genres = items
                        elif key == "styles":
                            ref.styles = items
            except Exception:
                pass

        return ref

    @staticmethod
    def _parse_rhyme_nodes(nodes: list[dict]) -> list[RhymeCategory]:
        """解析韵部树节点"""
        result = []
        for node in nodes:
            cat = RhymeCategory(
                id=node.get("id", ""),
                name=node.get("name", ""),
                description=node.get("description", ""),
                characters=node.get("characters", ""),
                notes=node.get("notes", ""),
                level=node.get("level", 0),
            )
            children = node.get("children", [])
            if children:
                cat.children = ReferenceAPI._parse_rhyme_nodes(children)
            result.append(cat)
        return result
