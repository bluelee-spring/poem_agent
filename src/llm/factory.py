"""LLM Provider 工厂 — 根据配置创建 Provider 实例"""

from typing import Optional
from src.llm.base import LLMProvider
from src.llm.deepseek import DeepSeekProvider
from src.llm.openai import OpenAIProvider

# 延迟导入避免循环依赖
_provider_instance: Optional[LLMProvider] = None


def create_provider() -> LLMProvider:
    """根据配置创建 LLM Provider 实例（单例）

    从环境变量读取:
      - LLM_PROVIDER: "deepseek" | "openai" (默认 "deepseek")
      - LLM_API_KEY:  API Key
      - LLM_BASE_URL: API 地址
      - LLM_MODEL:    模型名

    Returns:
        LLMProvider 实例
    """
    global _provider_instance

    if _provider_instance is not None:
        return _provider_instance

    # 延迟导入 config 避免循环
    from src.config import config

    provider_type = config.LLM_PROVIDER.lower()
    api_key = config.LLM_API_KEY
    base_url = config.LLM_BASE_URL
    model = config.LLM_MODEL

    if not api_key:
        raise RuntimeError(
            "未配置 LLM_API_KEY，请在 .env 中设置。\n"
            "DeepSeek: https://platform.deepseek.com/api_keys\n"
            "OpenAI:  https://platform.openai.com/api-keys"
        )

    if provider_type == "deepseek":
        _provider_instance = DeepSeekProvider(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com/v1",
            model=model or "deepseek-chat",
        )
    elif provider_type in ("openai", "openai_compatible"):
        _provider_instance = OpenAIProvider(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model=model or "gpt-4o-mini",
        )
    else:
        raise ValueError(
            f"不支持的 LLM_PROVIDER: {provider_type}，可选值: deepseek, openai"
        )

    return _provider_instance


def reset_provider():
    """重置 Provider 单例（用于测试或切换配置）"""
    global _provider_instance
    _provider_instance = None
