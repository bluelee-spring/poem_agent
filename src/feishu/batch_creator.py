"""批量诗歌创作流程

流程：搜热点 → LLM 筛选 → 逐话题创作 → 汇总 6 项 JSON → 写入飞书 Bitable

每次执行：从 ≥5 个热点话题中创作 20 首诗歌
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.tools.handlers.search import fetch_hot_topics, HotTopic
from src.llm.factory import create_provider
from src.llm.base import LLMProvider, Message
from src.api.poems import PoemsAPI, PoemParams
from src.tools.handlers.metrics import handle_analyze_poem
from src.feishu.client import FeishuClient
from src.config import config

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================
@dataclass
class PoemRecord:
    """单首诗歌的 6 项数据记录"""
    topic_title: str = ""       # 原始热搜标题
    topic_summary: str = ""     # 热点概要（LLM 生成）
    poem_params: str = ""       # 创作参数（体裁/题材/风格/情感/韵部/水平）
    poem_text: str = ""         # 诗作正文
    metrics_check: str = ""     # 格律校验结果
    ai_review: str = ""         # 机器评鉴（评分+评语）
    created_date: str = ""      # 创作日期 YYYY-MM-DD


@dataclass
class BatchResult:
    """批量创作结果"""
    total: int = 0
    success: int = 0
    failed: int = 0
    records: list[PoemRecord] = field(default_factory=list)


# ============================================================
# 核心流程
# ============================================================
class BatchPoemCreator:
    """批量诗歌创作器

    使用方式:
        creator = BatchPoemCreator(feishu_client)
        result = await creator.run(target_count=20)
    """

    POEMS_PER_TOPIC = 3  # 每话题最多创作几首

    def __init__(self, feishu: FeishuClient):
        self._feishu = feishu
        self._llm: LLMProvider | None = None
        self._poem_api: PoemsAPI | None = None

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = create_provider()
        return self._llm

    @property
    def poem_api(self) -> PoemsAPI:
        if self._poem_api is None:
            self._poem_api = PoemsAPI()
        return self._poem_api

    # ---- 主入口 ----
    async def run(
        self,
        target_count: int = 20,
        min_topics: int = 5,
        verbose: bool = True,
    ) -> BatchResult:
        """执行一次完整的批量创作"""
        logger.info(f"[批量创作] 开始，目标 {target_count} 首，最少 {min_topics} 个话题")

        # Phase 1: 采集并筛选热点
        topics = await self._collect_and_filter(min_topics)
        if verbose:
            logger.info(f"[批量创作] 筛选出 {len(topics)} 个话题")

        # Phase 2: 逐话题创作
        all_records: list[PoemRecord] = []
        poems_per = max(2, target_count // len(topics))
        poems_per = min(poems_per, self.POEMS_PER_TOPIC)

        for i, topic in enumerate(topics):
            if verbose:
                logger.info(f"[批量创作] 话题 {i+1}/{len(topics)}: {topic.title}")
            try:
                records = await self._create_for_topic(topic, count=poems_per)
                all_records.extend(records)
                if verbose:
                    logger.info(f"  -> 完成 {len(records)} 首")
            except Exception as e:
                logger.error(f"  -> 话题创作失败: {e}")
            if len(all_records) >= target_count:
                break

        # Phase 3: 写入飞书 Bitable
        success = 0
        for record in all_records:
            try:
                await self._feishu.write_poem_record(self._to_fields(record))
                success += 1
            except Exception as e:
                logger.error(f"写入 Bitable 失败: {e}")

        result = BatchResult(
            total=len(all_records),
            success=success,
            failed=len(all_records) - success,
            records=all_records,
        )
        logger.info(f"[批量创作] 完成: {result.success}/{result.total} 写入成功")
        return result

    # ---- Phase 1: 采集 + 筛选 ----
    async def _collect_and_filter(self, min_topics: int) -> list[HotTopic]:
        """采集热搜并用 LLM 筛选适合创作的话题"""
        all_topics = await fetch_hot_topics(limit=30, sources=["baidu", "weibo"])
        if len(all_topics) <= min_topics:
            return all_topics

        topics_text = "\n".join(
            f"{i+1}. [{t.source}] {t.title}"
            + (f"\n   摘要: {t.summary}" if t.summary else "")
            for i, t in enumerate(all_topics)
        )
        prompt = f"""你是诗歌创作编辑。从以下热搜中选出 {min_topics} 个最适合创作古典诗歌的话题。
选材标准：有情感深度（灾害、人文）> 自然科技 > 社会新闻 > 娱乐八卦。避免纯广告。
当前热搜：
{topics_text}
返回 JSON：{{"selected": [{{"index": 1, "reason": "理由"}}, ...]}}，仅返回 JSON。"""

        try:
            resp = await self.llm.chat([
                Message(role="system", content="你是诗歌编辑。仅返回 JSON。"),
                Message(role="user", content=prompt),
            ], temperature=0.3)
            import json, re
            match = re.search(r'\{[\s\S]*\}', resp.content)
            if match:
                data = json.loads(match.group())
                indices = [item["index"] - 1 for item in data.get("selected", [])]
                return [all_topics[i] for i in indices if 0 <= i < len(all_topics)]
        except Exception as e:
            logger.warning(f"LLM 筛选失败: {e}")

        return all_topics[:min_topics]

    # ---- Phase 2: 单话题创作 ----
    async def _create_for_topic(self, topic: HotTopic, count: int = 3) -> list[PoemRecord]:
        """为一个热点话题创作多首诗歌（不同体裁）"""
        records = []
        created_date = datetime.now().strftime("%Y-%m-%d")

        # A: 热点概要
        summary = await self._summarize_topic(topic)

        # B: 多组参数
        param_sets = await self._plan_params(topic, count)

        for params in param_sets:
            try:
                # C: 生成诗歌
                poem_params_obj = PoemParams(
                    poem_type=params.get("poem_type", "七言绝句"),
                    theme=params.get("theme", topic.title[:20]),
                    style=params.get("style", "沉郁顿挫"),
                    emotion=params.get("emotion", "感慨"),
                    rhyme=params.get("rhyme", "平水韵"),
                    creative_level=params.get("creative_level", "精诣"),
                )
                poems = await self.poem_api.generate_poem(poem_params_obj)
                poem_text = poems[0].content if poems else ""
                if not poem_text:
                    logger.warning(f"生成为空: {params.get('poem_type')}")
                    continue

                # D: 格律校验
                metrics = ""
                try:
                    metrics_result = await handle_analyze_poem({
                        "content": poem_text,
                        "rhyme": params.get("rhyme", "平水韵"),
                    })
                    if metrics_result.get("success"):
                        m = metrics_result["result"]
                        metrics = f"格律: {m.get('summary','')} | 合规: {m.get('is_compliant','?')}"
                except Exception:
                    metrics = "格律校验暂不可用"

                # E: LLM 评鉴
                review = await self._review_poem(topic, summary, params, poem_text)

                records.append(PoemRecord(
                    topic_title=f"[{topic.source}] {topic.title}",
                    topic_summary=summary,
                    poem_params=self._format_params(params),
                    poem_text=poem_text,
                    metrics_check=metrics[:500],
                    ai_review=review,
                    created_date=created_date,
                ))
            except Exception as e:
                logger.error(f"单首创作失败: {e}")

        return records

    # ---- LLM 辅助 ----
    async def _summarize_topic(self, topic: HotTopic) -> str:
        prompt = f"""用 2-3 句话概述以下热搜事件的核心内容、公众反应和情感基调（80字内）。
标题: {topic.title}
摘要: {topic.summary or '（无摘要）'}
直接输出文本，不要前缀。"""
        resp = await self.llm.chat([
            Message(role="system", content="你是新闻编辑。简洁概述。"),
            Message(role="user", content=prompt),
        ], temperature=0.3)
        return resp.content.strip()[:200]

    async def _plan_params(self, topic: HotTopic, count: int) -> list[dict]:
        prompt = f"""为话题推荐 {count} 组诗歌创作参数，体裁多样化。
话题: {topic.title} | 摘要: {topic.summary or '无'}
每组: poem_type(五言绝句/五言律诗/七言绝句/七言律诗/小令/中调)、theme(20字)、style、emotion、rhyme(诗用平水韵，词用词林正韵)、creative_level(固定精诣)
返回 JSON: {{"params": [{{...}}, ...]}}，仅 JSON。"""
        resp = await self.llm.chat([
            Message(role="system", content="你是诗歌创作顾问。仅返回 JSON。"),
            Message(role="user", content=prompt),
        ], temperature=0.7)
        import json, re
        match = re.search(r'\{[\s\S]*\}', resp.content)
        if match:
            data = json.loads(match.group())
            return data.get("params", [])[:count]
        return [{"poem_type": "七言绝句", "theme": topic.title[:20],
                 "style": "沉郁顿挫", "emotion": "感慨",
                 "rhyme": "平水韵", "creative_level": "精诣"}]

    async def _review_poem(self, topic: HotTopic, summary: str, params: dict, poem: str) -> str:
        prompt = f"""评鉴以下诗作（80字内，含评分）：
热点: {topic.title} | 概要: {summary} | 参数: {self._format_params(params)}
诗作: {poem}
格式: 评分 X.X/10，评语。"""
        resp = await self.llm.chat([
            Message(role="system", content="你是诗歌评鉴专家。简洁评鉴。"),
            Message(role="user", content=prompt),
        ], temperature=0.3)
        return resp.content.strip()[:300]

    # ---- 工具 ----
    @staticmethod
    def _format_params(params: dict) -> str:
        return (f"体裁: {params.get('poem_type','?')} | "
                f"题材: {params.get('theme','?')} | "
                f"风格: {params.get('style','?')} | "
                f"情感: {params.get('emotion','?')} | "
                f"韵部: {params.get('rhyme','?')} | "
                f"水平: {params.get('creative_level','精诣')}")

    @staticmethod
    def _to_fields(record: PoemRecord) -> dict[str, str]:
        return {
            "热点概要": record.topic_summary,
            "创作参数": record.poem_params,
            "诗作": record.poem_text,
            "格律校验": record.metrics_check,
            "机器评鉴": record.ai_review,
            "创作日期": record.created_date,
        }
