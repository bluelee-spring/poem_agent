"""工具注册中心 — 管理所有工具的注册、查找和执行"""

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Handler 类型：接收 arguments dict，返回结果 dict
ToolHandler = Callable[[dict[str, Any]], Any]


class ToolRegistry:
    """工具注册中心

    每个工具由两部分组成:
      - schema: OpenAI function calling 格式的 JSON Schema（给 LLM 看）
      - handler: 实际执行的函数（给 Agent 调用）

    使用方式:
        registry = ToolRegistry()
        registry.register(schema, handler)
        schemas = registry.get_all_schemas()    # 传给 LLM
        result = await registry.execute("tool_name", {"arg": "val"})
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}  # name -> {"schema": ..., "handler": ...}

    def register(self, schema: dict, handler: ToolHandler) -> None:
        """注册一个工具

        Args:
            schema: OpenAI function calling 格式的工具定义
            handler: 工具执行函数，接收 arguments dict，返回任意结果
        """
        name = schema["function"]["name"]
        if name in self._tools:
            logger.warning(f"工具 '{name}' 已注册，将被覆盖")
        self._tools[name] = {"schema": schema, "handler": handler}
        logger.debug(f"工具已注册: {name}")

    def register_batch(self, tools: list[tuple[dict, ToolHandler]]) -> None:
        """批量注册工具"""
        for schema, handler in tools:
            self.register(schema, handler)

    def get_schema(self, name: str) -> Optional[dict]:
        """获取指定工具的 schema"""
        tool = self._tools.get(name)
        return tool["schema"] if tool else None

    def get_all_schemas(self) -> list[dict]:
        """获取所有已注册工具的 schema 列表（传给 LLM）"""
        return [info["schema"] for info in self._tools.values()]

    def get_handler(self, name: str) -> Optional[ToolHandler]:
        """获取指定工具的 handler"""
        tool = self._tools.get(name)
        return tool["handler"] if tool else None

    def list_tools(self) -> list[str]:
        """列出所有已注册工具的名称"""
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """执行指定工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            包含 success 和 result 或 error 的字典

        Raises:
            ValueError: 工具未注册
        """
        handler = self.get_handler(name)
        if handler is None:
            error_msg = f"未知工具: {name}，可用工具: {self.list_tools()}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        logger.info(f"执行工具: {name}({_truncate_args(arguments)})")
        try:
            result = handler(arguments)
            # 支持 async handler
            import inspect
            if inspect.iscoroutine(result):
                result = await result
            logger.info(f"工具 {name} 执行成功")
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"工具 {name} 执行失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


def _truncate_args(args: dict, max_len: int = 200) -> str:
    """截断参数显示"""
    s = json.dumps(args, ensure_ascii=False)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def create_default_registry() -> ToolRegistry:
    """创建空的工具注册中心

    Schema 和 handler 由各个 handler 模块的 register_handlers() 统一注册，
    此处不再预注册占位 handler。
    """
    return ToolRegistry()
