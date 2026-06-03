"""诗歌评鉴器 - 对多首候选诗进行质量评分和排序"""

from dataclasses import dataclass, field
from src.api.poems import Poem


@dataclass
class RankedPoem:
    poem: Poem
    score: float           # 0-1 总分
    scores: dict[str, float] = field(default_factory=dict)  # 各维度分数
    feedback: str = ""     # 评语


class PoemEvaluator:
    """诗歌质量评鉴器"""

    # 评鉴维度和权重
    CRITERIA = {
        "意境": 0.25,
        "语言": 0.25,
        "韵律": 0.20,
        "切题": 0.15,
        "创新": 0.15,
    }

    async def rank(self, poems: list[Poem]) -> list[RankedPoem]:
        """
        对候选诗歌列表进行评鉴排序。
        返回按 score 降序排列的列表。
        """
        if not poems:
            return []

        ranked = []
        for poem in poems:
            # 评估单首诗
            scores = self._evaluate_single(poem)
            weighted = sum(
                scores.get(dim, 0) * weight
                for dim, weight in self.CRITERIA.items()
            )
            ranked.append(RankedPoem(
                poem=poem,
                score=round(weighted, 3),
                scores=scores,
                feedback=self._generate_feedback(poem, scores),
            ))

        # 按总分降序
        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked

    def _evaluate_single(self, poem: Poem) -> dict[str, float]:
        """
        对单首诗逐维度评分（0-1）。
        MVP 阶段使用规则评分，后续可接入 LLM。
        """
        scores = {}
        content = poem.content

        # 意境：有内容即可得基础分
        scores["意境"] = self._score_atmosphere(content)

        # 语言：看用词丰富度
        scores["语言"] = self._score_language(content)

        # 韵律：检查是否有韵脚标记
        scores["韵律"] = self._score_rhyme(poem)

        # 切题：有 title 表明有主题意识
        scores["切题"] = 0.7 if poem.title else 0.5

        # 创新：检查是否有生僻词或独特表达
        scores["创新"] = self._score_novelty(content)

        return scores

    def _score_atmosphere(self, content: str) -> float:
        """基于内容的意境评分"""
        if not content:
            return 0.3
        lines = [l for l in content.split("\n") if l.strip()]
        if len(lines) >= 4:
            return 0.8
        elif len(lines) >= 2:
            return 0.6
        return 0.4

    def _score_language(self, content: str) -> float:
        """基于用词的丰富度评分"""
        if not content:
            return 0.3
        chars = set(content.replace("\n", "").replace(" ", ""))
        unique_ratio = len(chars) / max(len(content), 1)
        # 独特字比例越高，语言越丰富（但有上限）
        return min(unique_ratio * 2, 1.0)

    def _score_rhyme(self, poem: Poem) -> float:
        """韵律评分"""
        # 从 raw 中检查是否有韵脚信息
        raw = poem.raw
        if raw.get("rhyme") or raw.get("rhyme_scheme"):
            return 0.9
        # 简单检测：看每行末字是否有相同韵母（需要后续增强）
        return 0.6

    def _score_novelty(self, content: str) -> float:
        """创新度评分"""
        if not content:
            return 0.3
        # 简单策略：内容长度适中得高分（太短没内容，太长可能啰嗦）
        length = len(content)
        if 40 <= length <= 200:
            return 0.8
        elif 20 <= length < 40:
            return 0.6
        return 0.5

    def _generate_feedback(self, poem: Poem, scores: dict[str, float]) -> str:
        """生成评语"""
        parts = []
        if scores.get("意境", 0) > 0.7:
            parts.append("意境深远")
        if scores.get("语言", 0) > 0.7:
            parts.append("用词典雅")
        if scores.get("韵律", 0) > 0.7:
            parts.append("韵律和谐")
        if scores.get("切题", 0) > 0.7:
            parts.append("紧扣主题")
        if scores.get("创新", 0) > 0.7:
            parts.append("别出心裁")

        if not parts:
            return "中规中矩"
        return "、".join(parts[:3])
