"""测试 send_to_chat"""
import asyncio
from dotenv import load_dotenv
load_dotenv()
from src.feishu.client import FeishuClient
import os

async def main():
    c = FeishuClient()
    chat_id = os.getenv("FEISHU_FORWARD_CHAT_ID", "")
    try:
        r = await c.send_to_chat(chat_id, "测试转发 - 诗千家智能体")
        print("OK:", r)
    except Exception as e:
        print("FAIL:", e)

asyncio.run(main())
