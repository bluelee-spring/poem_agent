"""日志模块 — 统一的日志配置和输出"""

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "poem_agent",
    level: str = "INFO",
    log_file: str | None = None,
    rich: bool = True,
) -> logging.Logger:
    """配置并返回一个 logger 实例。

    Args:
        name: logger 名称
        level: 日志级别 (DEBUG / INFO / WARNING / ERROR)
        log_file: 日志文件路径，None 表示仅输出到控制台
        rich: 是否使用 RichHandler 美化输出

    Returns:
        配置好的 logging.Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 handler
    if rich:
        try:
            from rich.logging import RichHandler
            console_handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
                markup=True,
            )
        except ImportError:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(_plain_formatter())
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(_plain_formatter())

    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(console_handler)

    # 文件 handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # 文件记录更详细
        file_handler.setFormatter(_detailed_formatter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "poem_agent") -> logging.Logger:
    """获取已有的 logger，如不存在则创建默认配置"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        from src.config import config
        return setup_logger(
            name=name,
            level=config.LOG_LEVEL,
            log_file=config.LOG_FILE,
        )
    return logger


def _plain_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _detailed_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
