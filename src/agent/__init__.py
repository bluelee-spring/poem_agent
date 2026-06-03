"""Agent 模块 — 控制器 + 参数选择 + 评鉴（保留旧模块兼容）"""

from src.agent.controller import PoemController, AgentResult
from src.agent.selector import ParamSelector, SelectorResult
from src.agent.evaluator import PoemEvaluator, RankedPoem
from src.agent.pipeline import PoemPipeline, PipelineResult

__all__ = [
    # 新架构
    "PoemController",
    "AgentResult",
    # 旧模块（兼容）
    "ParamSelector",
    "SelectorResult",
    "PoemEvaluator",
    "RankedPoem",
    "PoemPipeline",
    "PipelineResult",
]
