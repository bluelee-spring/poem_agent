"""参数选择器 - 从热点话题映射到诗歌创作参数

双引擎：
  1. LLM 引擎：调用大模型理解语义，智能推荐参数（需配置 LLM_API_KEY）
  2. 规则引擎：关键词匹配映射表（兜底）
"""

from dataclasses import dataclass
import json
import httpx

from src.api.poems import PoemParams
from src.config import config


# ============================================================
# 规则引擎：关键词 → 参数映射表（LLM 不可用时的兜底）
# ============================================================
TOPIC_MAPPINGS: dict[str, dict] = {
    "春":     {"poem_type": "五言律诗", "style": "清新", "emotion": "赞美", "rhyme": "平水"},
    "秋":     {"poem_type": "五言律诗", "style": "沉郁", "emotion": "感慨", "rhyme": "平水"},
    "山":     {"poem_type": "五言绝句", "style": "清新", "emotion": "赞美", "rhyme": "平水"},
    "水":     {"poem_type": "五言绝句", "style": "清新", "emotion": "赞美", "rhyme": "平水"},
    "思乡":   {"poem_type": "七言律诗", "style": "婉约", "emotion": "感慨", "rhyme": "词林"},
    "离别":   {"poem_type": "七言绝句", "style": "沉郁", "emotion": "伤感", "rhyme": "词林"},
    "爱国":   {"poem_type": "七言律诗", "style": "豪放", "emotion": "赞美", "rhyme": "平水"},
    "边塞":   {"poem_type": "七言律诗", "style": "豪放", "emotion": "感慨", "rhyme": "平水"},
    "战争":   {"poem_type": "七言律诗", "style": "豪放", "emotion": "悲愤", "rhyme": "平水"},
    "爱情":   {"poem_type": "七言绝句", "style": "婉约", "emotion": "思念", "rhyme": "词林"},
    "友情":   {"poem_type": "五言律诗", "style": "典雅", "emotion": "赞美", "rhyme": "平水"},
    "节日":   {"poem_type": "七言律诗", "style": "典雅", "emotion": "喜悦", "rhyme": "中华"},
    "自然":   {"poem_type": "五言绝句", "style": "清新", "emotion": "赞美", "rhyme": "平水"},
    "咏物":   {"poem_type": "五言律诗", "style": "典雅", "emotion": "赞美", "rhyme": "平水"},
    "怀古":   {"poem_type": "七言律诗", "style": "沉郁", "emotion": "感慨", "rhyme": "平水"},
    "田园":   {"poem_type": "五言律诗", "style": "清新", "emotion": "闲适", "rhyme": "平水"},
    "哲理":   {"poem_type": "五言绝句", "style": "典雅", "emotion": "思考", "rhyme": "平水"},
    "民生":   {"poem_type": "七言律诗", "style": "沉郁", "emotion": "感慨", "rhyme": "中华"},
    "科技":   {"poem_type": "七言绝句", "style": "豪放", "emotion": "赞美", "rhyme": "中华"},
    "青春":   {"poem_type": "七言绝句", "style": "清新", "emotion": "赞美", "rhyme": "平水"},
    "励志":   {"poem_type": "七言律诗", "style": "豪放", "emotion": "激昂", "rhyme": "平水"},
    "雪":     {"poem_type": "五言绝句", "style": "清新", "emotion": "赞美", "rhyme": "平水"},
    "月":     {"poem_type": "五言绝句", "style": "婉约", "emotion": "思念", "rhyme": "平水"},
    "花":     {"poem_type": "五言律诗", "style": "典雅", "emotion": "赞美", "rhyme": "平水"},
    "酒":     {"poem_type": "七言绝句", "style": "豪放", "emotion": "感慨", "rhyme": "平水"},
    "梦":     {"poem_type": "七言绝句", "style": "婉约", "emotion": "思念", "rhyme": "词林"},
    "风":     {"poem_type": "五言绝句", "style": "清新", "emotion": "赞美", "rhyme": "平水"},
    "夜":     {"poem_type": "五言律诗", "style": "沉郁", "emotion": "思考", "rhyme": "平水"},
}

# 可选的诗体/风格/情感列表（用于 LLM prompt 约束）
POEM_TYPES = ["五言律诗", "七言律诗", "五言绝句", "七言绝句"]
STYLES = ["清新", "沉郁", "豪放", "婉约", "典雅"]
EMOTIONS = ["赞美", "感慨", "思念", "伤感", "闲适", "悲愤", "激昂", "喜悦", "思考", "讽刺", "忧虑"]
RHYMES = ["平水", "词林", "中华"]


@dataclass
class SelectorResult:
    params: PoemParams
    confidence: float
    reasoning: str
    engine: str = ""  # "llm" 或 "rule"


# ============================================================
# LLM 引擎
# ============================================================

LLM_SYSTEM_PROMPT = """你是一位精通中国古典诗歌的文学教授。根据用户给出的话题或热点事件，你需要推荐最合适的诗歌创作参数。

请分析话题的情感倾向、严肃程度、内容领域，然后选择：
- poem_type: 诗体。短小精悍的话题用绝句，宏大复杂的用律诗。
  - "五言律诗": 端庄典雅，适合写景、咏物、感怀
  - "七言律诗": 气势恢宏，适合议论、叙事、抒情
  - "五言绝句": 简洁凝练，适合哲理、瞬间感触
  - "七言绝句": 灵动飘逸，适合生活随感、轻松话题
- style: 风格。根据话题基调选择。
  - "清新": 轻松愉快、自然风光
  - "沉郁": 沉重、严肃、社会问题、不幸事件
  - "豪放": 宏大、正面、成就、鼓舞人心
  - "婉约": 细腻、情感、私人话题
  - "典雅": 正式、文化、学术
- emotion: 情感倾向
  - "赞美": 正面、歌颂
  - "感慨": 感叹、反思
  - "思念": 怀念、追忆
  - "伤感": 悲伤、遗憾
  - "讽刺": 批评、不满、社会问题
  - "忧虑": 担忧、关切
  - "闲适": 平和、悠然
  - "激昂": 激励、奋发
  - "喜悦": 高兴、庆祝
- rhyme: 韵部。"平水"（平水韵）/ "词林"（词林正韵）/ "中华"（中华新韵）

请仅返回一个 JSON 对象，不要有任何其他文字：
{"poem_type": "...", "style": "...", "emotion": "...", "rhyme": "..."}"""


class LLMSelector:
    """基于大模型的参数选择器"""

    def __init__(self):
        self.api_key = config.LLM_API_KEY
        self.base_url = config.LLM_BASE_URL.rstrip("/")
        self.model = config.LLM_MODEL

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def select(self, topic: str) -> SelectorResult:
        """调用 LLM 分析话题，返回推荐参数"""
        if not self.available:
            raise RuntimeError("LLM 不可用：未配置 LLM_API_KEY")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": f"请为以下话题推荐诗歌创作参数：\n\n{topic}"},
            ],
            "temperature": 0.3,
            "max_tokens": 200,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"].strip()
        # 提取 JSON（可能被 markdown 代码块包裹）
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        llm_result = json.loads(content)

        # 校验并构造 PoemParams
        params = PoemParams(
            poem_type=self._validate(llm_result.get("poem_type", ""), POEM_TYPES, "五言律诗"),
            theme=topic,
            style=self._validate(llm_result.get("style", ""), STYLES, "典雅"),
            emotion=self._validate(llm_result.get("emotion", ""), EMOTIONS, "感慨"),
            rhyme=self._validate(llm_result.get("rhyme", ""), RHYMES, "平水"),
            title=topic,
            keywords=[topic],
        )

        return SelectorResult(
            params=params,
            confidence=0.9,
            reasoning=f"LLM 分析: 「{topic}」→ {params.poem_type}/{params.style}/{params.emotion}",
            engine="llm",
        )

    @staticmethod
    def _validate(value: str, allowed: list[str], default: str) -> str:
        """校验值在允许列表中，否则返回默认值"""
        if value in allowed:
            return value
        # 模糊匹配
        for a in allowed:
            if a in value or value in a:
                return a
        return default


# ============================================================
# 规则引擎（兜底）
# ============================================================

class RuleSelector:
    """基于关键词匹配的规则选择器（兜底）"""

    def select(self, topic: str, keywords: list[str] | None = None) -> SelectorResult:
        result = self._rule_match(topic)
        if result and result.confidence >= 0.7:
            return result

        return self._fuzzy_match(topic, keywords or [])

    def _rule_match(self, topic: str) -> SelectorResult | None:
        topic_lower = topic.lower().strip()
        for keyword, mapping in TOPIC_MAPPINGS.items():
            if keyword in topic_lower or topic_lower in keyword:
                params = PoemParams(
                    poem_type=mapping.get("poem_type", "五言律诗"),
                    theme=topic,
                    style=mapping.get("style", ""),
                    emotion=mapping.get("emotion", ""),
                    rhyme=mapping.get("rhyme", ""),
                    title=topic,
                    keywords=[topic],
                )
                return SelectorResult(
                    params=params,
                    confidence=0.85,
                    reasoning=f"规则匹配: 「{topic}」→ {params.poem_type}/{params.style}",
                    engine="rule",
                )
        return None

    def _fuzzy_match(self, topic: str, keywords: list[str]) -> SelectorResult:
        all_keywords = [topic] + keywords
        poem_types, styles, emotions, rhymes = [], [], [], []

        for kw in all_keywords:
            for keyword, mapping in TOPIC_MAPPINGS.items():
                if keyword in kw or kw in keyword:
                    poem_types.append(mapping.get("poem_type", ""))
                    styles.append(mapping.get("style", ""))
                    emotions.append(mapping.get("emotion", ""))
                    rhymes.append(mapping.get("rhyme", ""))

        from collections import Counter
        def most_common(items: list[str], default: str) -> str:
            return Counter([i for i in items if i]).most_common(1)[0][0] if items else default

        params = PoemParams(
            poem_type=most_common(poem_types, "五言律诗"),
            theme=topic,
            style=most_common(styles, "清新"),
            emotion=most_common(emotions, "赞美"),
            rhyme=most_common(rhymes, "平水"),
            title=topic,
            keywords=all_keywords,
        )
        return SelectorResult(
            params=params,
            confidence=0.4,
            reasoning=f"模糊匹配: 「{topic}」→ {params.poem_type}/{params.style}",
            engine="rule",
        )


# ============================================================
# 统一入口
# ============================================================

class ParamSelector:
    """诗歌创作参数选择器（LLM 优先，规则兜底）"""

    POEM_TYPES = POEM_TYPES
    STYLES = STYLES
    EMOTIONS = EMOTIONS

    def __init__(self):
        self._llm = LLMSelector()
        self._rule = RuleSelector()
        self._llm_failed = False  # 一旦 LLM 失败就不再尝试

    async def choose_params(
        self,
        topic_hint: str | None = None,
        keywords: list[str] | None = None,
    ) -> SelectorResult:
        if not topic_hint:
            topic_hint = "春"

        # 优先使用 LLM
        if self._llm.available and not self._llm_failed:
            try:
                result = await self._llm.select(topic_hint)
                return result
            except Exception as e:
                print(f"  [WARN] LLM 调用失败，回退到规则引擎: {e}")
                self._llm_failed = True

        # 规则引擎兜底
        return self._rule.select(topic_hint, keywords)

    def refine_params(self, params: PoemParams, feedback: str) -> PoemParams:
        try:
            idx = STYLES.index(params.style)
            params.style = STYLES[(idx + 1) % len(STYLES)]
        except ValueError:
            params.style = "豪放"
        try:
            idx = POEM_TYPES.index(params.poem_type)
            params.poem_type = POEM_TYPES[(idx + 1) % len(POEM_TYPES)]
        except ValueError:
            params.poem_type = "七言律诗"
        params.extra["refine_feedback"] = feedback
        return params
