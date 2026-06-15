"""热点写诗 Skill — 工作流定义

封装「根据网络热点自动创作诗歌并评鉴」的完整 Skill 定义。
"""

from src.skills.base import Skill
from src.skills.hot_topic_poem.prompt import SYSTEM_PROMPT


def create_skill() -> Skill:
    """创建热点写诗 Skill 实例

    Returns:
        Skill 实例，包含完整的工作流定义
    """
    return Skill(
        name="hot_topic_poem",
        description="根据微博/百度网络热点，自动创作古典诗歌并进行专业评鉴",
        system_prompt=SYSTEM_PROMPT,
        tool_names=[
            "search_hot_topics",   # 采集微博/百度热搜
            "web_search",           # 搜索热点背景信息
            "get_references",       # 查询韵部树/场景分类
            "generate_poem",        # 调用诗千家 API 生成作品
            "analyze_poem",         # 搜韵网格律校验
            "save_poem",            # 保存到本地历史
            "get_history",          # 查询创作历史
        ],
    )
