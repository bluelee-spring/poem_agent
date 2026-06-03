"""兼容转发 — 原 src/config.py 已迁移至 src/config/settings.py

保留此文件以确保现有 import 不受影响。
"""

# 转发到新的包结构
from src.config.settings import Config, config  # noqa: F401
