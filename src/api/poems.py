"""诗歌 API 封装 - 生成、检索、精修、填句

实际诗歌生成端点:
  POST /template/template-external-model  (TemplateRequest schema)
    - model: str | null      可选模型名，如 "deepseek-chat"
    - prompt: PromptTemplate  (见下方)
    - user_id: str | null    用户ID

  PromptTemplate:
    poem_type              : str    (必填) 诗体，如"五言律诗"
    theme                  : str    主题
    style                  : str    风格，如"豪放"
    emotion                : str    情感
    imagery                : str    意象
    allusions              : str    用典
    additional_requirements: str    额外要求
    hidden                 : str    藏头诗
    rhyme                  : str    韵部
    title                  : str    题目
    creative_level         : str    创作水平描述
    personalized_info      : str    个性化信息
"""

from dataclasses import dataclass, field
from typing import Any
from src.api.client import get_client


@dataclass
class PoemParams:
    """诗歌创作参数（对应 PromptTemplate）"""
    poem_type: str = ""           # 诗体（必填），如"五言律诗"
    theme: str = ""               # 主题
    style: str = ""               # 风格
    emotion: str = ""             # 情感
    imagery: str = ""             # 意象
    allusions: str = ""           # 用典
    additional_requirements: str = ""  # 额外要求
    hidden: str = ""              # 藏头诗
    rhyme: str = ""               # 韵部
    title: str = ""               # 题目
    creative_level: str = ""      # 创作水平
    personalized_info: str = ""   # 个性化信息
    model: str = ""               # 模型名（可选）
    keywords: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Poem:
    """诗歌结果"""
    id: str = ""
    title: str = ""
    content: str = ""
    author_style: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class PoemsAPI:
    """诗千家诗歌 API"""

    async def generate_poem(self, params: PoemParams) -> list[Poem]:
        """
        调用外部 AI 模型生成诗歌——核心接口。
        使用 /template/template-external-model 端点。
        """
        client = get_client()
        body = self._build_template_body(params)
        resp = await client.post("/template/template-external-model", json=body)
        if resp.status_code != 200:
            detail = resp.text
            try:
                detail = resp.json()
            except Exception:
                pass
            raise RuntimeError(
                f"generate_poem 失败 (HTTP {resp.status_code}): {detail}\n"
                f"请求体: {body}"
            )
        data = resp.json()
        return self._parse_poems(data)

    async def retrieve_poems(self, params: PoemParams) -> list[Poem]:
        """兼容旧接口：实际调用 generate_poem"""
        return await self.generate_poem(params)

    async def refine_poem(self, poem_id: str, instruction: str) -> Poem:
        """精修已有诗歌"""
        client = get_client()
        body = {
            "poem_id": poem_id,
            "prompt": instruction,
        }
        resp = await client.post("/poems/refine-poems", json=body)
        resp.raise_for_status()
        return self._parse_single(resp.json())

    async def filling_sentence(self, context: str, position: str) -> Poem:
        """填句补全"""
        client = get_client()
        body = {
            "context": context,
            "position": position,
        }
        resp = await client.post("/poems/filling-sentence", json=body)
        resp.raise_for_status()
        return self._parse_single(resp.json())

    def _build_template_body(self, params: PoemParams) -> dict:
        """构建 TemplateRequest 请求体"""
        prompt: dict[str, Any] = {"poem_type": params.poem_type}
        if params.theme:
            prompt["theme"] = params.theme
        if params.style:
            prompt["style"] = params.style
        if params.emotion:
            prompt["emotion"] = params.emotion
        if params.imagery:
            prompt["imagery"] = params.imagery
        if params.allusions:
            prompt["allusions"] = params.allusions
        if params.additional_requirements:
            prompt["additional_requirements"] = params.additional_requirements
        if params.hidden:
            prompt["hidden"] = params.hidden
        if params.rhyme:
            prompt["rhyme"] = params.rhyme
        if params.title:
            prompt["title"] = params.title
        if params.creative_level:
            prompt["creative_level"] = params.creative_level
        if params.personalized_info:
            prompt["personalized_info"] = params.personalized_info

        body: dict[str, Any] = {"prompt": prompt}
        if params.model:
            body["model"] = params.model
        return body

    def _parse_poems(self, data: dict) -> list[Poem]:
        """解析 API 返回的诗歌。支持多种格式：
        - {"title": "...", "content": "..."}  (template-external-model)
        - {"poems": [...]} / {"results": [...]} / {"data": [...]}
        """
        # 格式1: 单首诗 {"title": "...", "content": "..."}
        if isinstance(data, dict) and "content" in data:
            return [self._parse_single(data)]

        # 格式2: 数组包装
        items = data.get("poems") or data.get("results") or data.get("data") or []
        if isinstance(items, dict):
            items = [items]
        if not items and isinstance(data, dict) and data.get("poem"):
            items = [data]
        return [self._parse_single(item) for item in items]

    @staticmethod
    def _parse_single(data: dict) -> Poem:
        return Poem(
            id=data.get("id", ""),
            title=data.get("title", ""),
            content=data.get("content", "") or data.get("poem", ""),
            author_style=data.get("author_style", ""),
            raw=data,
        )
