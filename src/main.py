"""诗千家智能体 — CLI 入口（新架构）

命令:
  agent    LLM 驱动的智能创作（默认）
  auth     获取 OAuth 登录链接
  check    检查认证状态
  hot      采集热点话题
  history  查看创作历史

环境变量（.env）:
  POEM_ACCESS_TOKEN  诗千家 API Token（必须）
  LLM_API_KEY        LLM API Key（必须）
  LLM_PROVIDER       deepseek | openai（默认 deepseek）
  LLM_MODEL          模型名（默认 deepseek-chat）
"""

import asyncio
import sys
import argparse

from dotenv import load_dotenv

# 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()


async def cmd_agent(topic: str | None, verbose: bool):
    """LLM 驱动的智能创作"""
    from src.agent.controller import PoemController
    from src.config import config

    # 前置检查
    if not config.POEM_ACCESS_TOKEN:
        print("[!] 未配置 POEM_ACCESS_TOKEN，请先运行: poem-agent auth")
        return
    if not config.LLM_API_KEY:
        print("[!] 未配置 LLM_API_KEY，请在 .env 中设置")
        return

    controller = PoemController()

    if topic is None:
        print("诗千家智能体 v0.2.2")
        print("输入 'exit' 或 'quit' 退出\n")
        while True:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见～")
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("再见～")
                break
            await controller.run(user_input, verbose=verbose)
    else:
        result = await controller.run(topic, verbose=verbose)
        if not result.success:
            print(f"[!] 执行失败: {result.error}")


async def cmd_auth():
    """获取 OAuth 登录链接"""
    from src.api.auth import AuthManager

    auth = AuthManager()
    print("正在获取登录链接...")
    try:
        auth_url = await auth.get_auth_url(debug=True)
        print(f"\n请在浏览器中打开以下链接完成登录：\n{auth_url}")
        print("\n登录完成后，将 token 写入 .env 文件的 POEM_ACCESS_TOKEN 字段。")
    except Exception as e:
        print(f"获取登录链接失败: {e}")


async def cmd_check():
    """检查认证状态"""
    from src.api.auth import AuthManager
    from src.config import config

    if not config.POEM_ACCESS_TOKEN:
        print("[!] 未设置 POEM_ACCESS_TOKEN")
        return

    auth = AuthManager()
    ok = await auth.verify_token()
    if ok:
        print("[OK] Token 有效，已认证")
    else:
        print("[!] Token 无效或已过期")


async def cmd_hot(limit: int):
    """采集热点话题"""
    from src.collectors.hot_topics import HotTopicCollector

    collector = HotTopicCollector()
    print("正在采集热点...")
    topics = await collector.collect_all(limit=limit)

    if not topics:
        print("未获取到热点")
        return

    for t in topics:
        heat_str = f"({t.heat})" if t.heat else ""
        print(f"  [{t.source}] #{t.rank} {t.title} {heat_str}")


async def cmd_history(limit: int, topic: str | None):
    """查看创作历史"""
    from src.memory import get_history

    h = get_history()
    records = h.query(topic=topic, limit=limit)

    if not records:
        print("暂无创作记录")
        return

    for r in records:
        score_str = f"[{r.get('score', 'N/A')}]" if r.get('score') is not None else ""
        print(f"\n{'─'*40}")
        print(f"  {r.get('title', '(无题)')} {score_str}")
        print(f"  {r.get('content', '')}")
        if r.get('comment'):
            print(f"  评语: {r['comment']}")


def main():
    parser = argparse.ArgumentParser(
        description="诗千家智能体 — LLM 驱动的古典诗歌创作 Agent"
    )
    sub = parser.add_subparsers(dest="command")

    # agent（默认命令）
    agent_parser = sub.add_parser("agent", help="LLM 驱动的智能创作（默认）")
    agent_parser.add_argument("--topic", "-t", help="创作主题")
    agent_parser.add_argument("--quiet", "-q", action="store_true", help="简洁模式")

    sub.add_parser("auth", help="获取 OAuth 登录链接")
    sub.add_parser("check", help="检查认证状态")

    hot_parser = sub.add_parser("hot", help="采集热点话题")
    hot_parser.add_argument("--limit", "-n", type=int, default=20, help="数量上限")

    hist_parser = sub.add_parser("history", help="查看创作历史")
    hist_parser.add_argument("--limit", "-n", type=int, default=10, help="数量")
    hist_parser.add_argument("--topic", "-t", help="按主题筛选")

    args = parser.parse_args()

    if args.command == "auth":
        asyncio.run(cmd_auth())
    elif args.command == "check":
        asyncio.run(cmd_check())
    elif args.command == "hot":
        asyncio.run(cmd_hot(args.limit))
    elif args.command == "history":
        asyncio.run(cmd_history(args.limit, args.topic))
    elif args.command == "agent" or args.command is None:
        topic = getattr(args, "topic", None)
        verbose = not getattr(args, "quiet", False)
        asyncio.run(cmd_agent(topic, verbose))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
