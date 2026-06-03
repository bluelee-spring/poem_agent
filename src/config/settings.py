"""全局配置 — 从 .env 加载环境变量"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")


class Config:
    """全局配置，从环境变量读取"""

    # ================================================================
    # 诗千家 API
    # ================================================================
    POEM_BASE_URL: str = os.getenv("POEM_BASE_URL", "https://poem.pkudh.org")
    POEM_ACCESS_TOKEN: str = os.getenv("POEM_ACCESS_TOKEN", "")

    # ================================================================
    # LLM Provider
    # ================================================================
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL",
        "https://api.deepseek.com/v1" if os.getenv("LLM_PROVIDER", "deepseek") == "deepseek" else "https://api.openai.com/v1",
    )
    LLM_MODEL: str = os.getenv(
        "LLM_MODEL",
        "deepseek-chat" if os.getenv("LLM_PROVIDER", "deepseek") == "deepseek" else "gpt-4o-mini",
    )

    # ================================================================
    # Agent 参数
    # ================================================================
    N_CANDIDATES: int = int(os.getenv("N_CANDIDATES", "3"))     # 每轮生成候选诗歌数量
    QUALITY_THRESHOLD: float = float(os.getenv("QUALITY_THRESHOLD", "0.6"))  # 最低质量阈值
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))        # 最大重试次数

    # ================================================================
    # 日志
    # ================================================================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(_project_root / "data" / "app.log"))

    # ================================================================
    # 数据目录
    # ================================================================
    @property
    def data_dir(self) -> Path:
        d = _project_root / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ================================================================
    # 便捷方法
    # ================================================================
    @classmethod
    def is_authenticated(cls) -> bool:
        return bool(cls.POEM_ACCESS_TOKEN)

    @classmethod
    def has_llm(cls) -> bool:
        return bool(cls.LLM_API_KEY)


config = Config()
