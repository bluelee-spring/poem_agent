"""单次诗歌创作 Pipeline - Plan → Act → Observe → Replan"""

from dataclasses import dataclass, field
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.api.poems import PoemsAPI, PoemParams, Poem
from src.agent.selector import ParamSelector, SelectorResult
from src.agent.evaluator import PoemEvaluator, RankedPoem
from src.config import config

console = Console(force_terminal=False, legacy_windows=True)


@dataclass
class PipelineResult:
    """一次 Pipeline 执行结果"""
    success: bool
    topic: str = ""
    params: PoemParams | None = None
    best_poem: RankedPoem | None = None
    all_candidates: list[RankedPoem] = field(default_factory=list)
    retries: int = 0
    error: str = ""


class PoemPipeline:
    """
    单次诗歌创作流水线

    执行流程:
      Plan   → 选择创作参数（题材/体裁/风格/韵部）
      Act    → 调用 API 生成多首候选诗歌
      Observe→ 评鉴排序，选出最优
      Replan → 如果质量不达标，调整参数重试
    """

    def __init__(self):
        self.selector = ParamSelector()
        self.poems_api = PoemsAPI()
        self.evaluator = PoemEvaluator()

    async def run(
        self,
        topic_hint: str | None = None,
        keywords: list[str] | None = None,
        n_candidates: int | None = None,
    ) -> PipelineResult:
        """
        执行一次完整的诗歌创作流程。

        Args:
            topic_hint: 话题提示（如"春天"、"思乡"）
            keywords: 额外关键词
            n_candidates: 每轮生成候选数量，默认取 config 配置
        """
        n = n_candidates or config.N_CANDIDATES
        result = PipelineResult(success=False, topic=topic_hint or "默认")

        try:
            # ============================================
            # Step 1: PLAN - 选择创作参数
            # ============================================
            console.print(f"\n[bold cyan][PLAN][/] - 选择创作参数 (话题: {topic_hint or '自动'})")
            selection = await self.selector.choose_params(topic_hint, keywords)
            result.params = selection.params
            console.print(f"  置信度: {selection.confidence:.0%} | [{selection.engine}] {selection.reasoning}")
            console.print(f"  参数: poem_type={selection.params.poem_type}, "
                          f"theme={selection.params.theme}, "
                          f"style={selection.params.style}, "
                          f"emotion={selection.params.emotion}, "
                          f"rhyme={selection.params.rhyme}")

            # ============================================
            # Step 2: ACT - 调用 API 生成候选诗歌
            # ============================================
            for attempt in range(config.MAX_RETRIES + 1):
                result.retries = attempt
                console.print(f"\n[bold yellow][ACT][/] - 生成候选诗歌 (第 {attempt + 1} 轮, {n} 首)")

                # 生成多首候选
                candidates = await self._generate_candidates(selection.params, n, seed=attempt)

                if not candidates:
                    console.print("[red]  未获取到候选诗歌[/]")
                    if attempt < config.MAX_RETRIES:
                        selection.params = self.selector.refine_params(
                            selection.params, "无结果"
                        )
                        continue
                    result.error = "API 未返回任何诗歌"
                    return result

                # ============================================
                # Step 3: OBSERVE - 评鉴排序
                # ============================================
                console.print(f"\n[bold green][OBSERVE][/] - 评鉴 {len(candidates)} 首候选诗歌")
                ranked = await self.evaluator.rank(candidates)
                result.all_candidates = ranked

                # 打印排名
                self._print_ranking(ranked)

                best = ranked[0]

                # ============================================
                # Step 4: REPLAN - 判断是否需要重试
                # ============================================
                if best.score >= config.QUALITY_THRESHOLD:
                    console.print(f"\n[bold green][OK] 质量达标[/] ({best.score:.2f} >= {config.QUALITY_THRESHOLD})")
                    result.success = True
                    result.best_poem = best
                    return result

                console.print(
                    f"\n[bold yellow][RETRY][/] - 质量不达标 ({best.score:.2f} < {config.QUALITY_THRESHOLD})，调整参数重试"
                )
                if attempt < config.MAX_RETRIES:
                    selection.params = self.selector.refine_params(
                        selection.params, best.feedback
                    )

            # 耗尽重试次数，取最佳
            result.success = True
            result.best_poem = ranked[0]
            console.print(f"\n[yellow][WARN] 达重试上限，取当前最佳 (score={ranked[0].score:.2f})[/]")
            return result

        except Exception as e:
            result.error = str(e)
            console.print(f"\n[red][ERR] Pipeline 异常: {e}[/]")
            return result

    async def _generate_candidates(
        self, params: PoemParams, n: int, seed: int = 0
    ) -> list[Poem]:
        """调用 API 生成 n 首候选诗歌"""
        candidates = []
        for i in range(n):
            # 每首用不同的 seed/参数变化
            p = PoemParams(
                poem_type=params.poem_type,
                theme=params.theme,
                style=params.style,
                emotion=params.emotion,
                rhyme=params.rhyme,
                title=params.title,
                keywords=params.keywords,
                extra={**params.extra, "seed": seed * n + i},
            )
            try:
                poems = await self.poems_api.retrieve_poems(p)
                candidates.extend(poems)
            except RuntimeError as e:
                # RuntimeError 来自 poems.py 中非 200 响应（含 500），直接抛出终止
                raise
            except Exception as e:
                console.print(f"  [yellow]生成第 {i + 1} 首失败: {e}[/]")

        return candidates

    def _print_ranking(self, ranked: list[RankedPoem]):
        """用 Rich 表格打印排名"""
        table = Table(title="候选诗歌排名", show_lines=False)
        table.add_column("#", style="dim", width=3)
        table.add_column("评分", style="cyan", width=6)
        table.add_column("标题/首句", style="green", width=30)
        table.add_column("评语", style="yellow", width=25)

        for i, r in enumerate(ranked[:5]):  # 只展示前 5
            content_preview = (
                r.poem.title
                or r.poem.content.replace("\n", " ")[:30]
                or "(无内容)"
            )
            table.add_row(
                str(i + 1),
                f"{r.score:.2f}",
                content_preview,
                r.feedback,
            )

        console.print(table)

        # 打印每首候选诗的完整内容
        console.print()
        for i, r in enumerate(ranked[:3]):
            console.print(f"[bold]#{i+1} (评分: {r.score:.2f})[/] {r.feedback}")
            console.print(f"  {r.poem.content}")
            console.print()
