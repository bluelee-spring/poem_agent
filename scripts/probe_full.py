"""诗千家 API 全面参数探测脚本

逐步探测 /template/template-external-model 端点接受的参数范围。
每个维度独立测试，记录 API 是否接受（HTTP 200 = 接受，400/422 = 拒绝）。

用法:
    python scripts/probe_full.py
"""

import asyncio
import json
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("POEM_ACCESS_TOKEN", "")

BASE_URL = "https://poem.pkudh.org"
ENDPOINT = "/template/template-external-model"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
}

# 基础参数（每次只变一个维度，其余固定）
BASE_PROMPT = {
    "poem_type": "五言律诗",
    "theme": "春天",
}


async def probe(label: str, prompt_overrides: dict) -> tuple[int, str, str]:
    """探测一个参数组合，返回 (状态码, 诗歌预览, 错误信息)"""
    body = {
        "prompt": {**BASE_PROMPT, **prompt_overrides},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{BASE_URL}{ENDPOINT}", json=body, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", "") or data.get("poem", "")
                return 200, content[:80].replace("\n", " "), ""
            else:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text[:200]
                return resp.status_code, "", str(detail)
        except Exception as e:
            return -1, "", str(e)


async def probe_dimension(name: str, values: list[str], param: str):
    """探测一个维度的所有候选值"""
    print(f"\n{'='*60}")
    print(f"探测维度: {name} (参数: {param})")
    print(f"{'='*60}")

    accepted = []
    rejected = []
    errors = []

    for val in values:
        status, preview, detail = await probe(
            f"{param}={val}",
            {param: val},
        )
        symbol = "✅" if status == 200 else ("❌" if status >= 400 else "⚠️")
        line = f"  {symbol} [{status}] {param}={val}"
        if preview:
            line += f"  → {preview}"
        if detail:
            line += f"  {detail[:100]}"
        print(line)

        if status == 200:
            accepted.append(val)
        elif status >= 400:
            rejected.append(val)
        else:
            errors.append(val)

    print(f"\n  接受: {accepted}")
    print(f"  拒绝: {rejected}")
    if errors:
        print(f"  错误: {errors}")
    return accepted, rejected


async def main():
    if not TOKEN:
        print("[!] 未配置 POEM_ACCESS_TOKEN，请先在 .env 中设置")
        return

    print("诗千家 API 全面参数探测")
    print(f"端点: {ENDPOINT}")
    print(f"基础参数: {json.dumps(BASE_PROMPT, ensure_ascii=False)}")

    # ============================================================
    # 维度 1: 诗体 / 体裁 (poem_type)
    # ============================================================
    poem_types = [
        # 诗
        "五言律诗", "七言律诗", "五言绝句", "七言绝句",
        "五言古诗", "七言古诗", "排律",
        # 词
        "词", "浣溪沙", "菩萨蛮", "水调歌头", "念奴娇",
        "蝶恋花", "满江红", "鹧鸪天", "临江仙", "如梦令",
        # 曲
        "曲", "天净沙", "山坡羊", "沉醉东风",
        # 文言古文
        "文言古文", "赋", "记", "序",
        # 外国文学
        "外国文学",
        # 其他可能
        "古风", "乐府", "现代诗",
    ]
    await probe_dimension("诗体/体裁", poem_types, "poem_type")

    # ============================================================
    # 维度 2: 韵部 (rhyme)
    # ============================================================
    rhymes = [
        "平水", "词林", "中华",
        "平水韵", "词林正韵", "中华新韵", "中原音韵",
        # 平水韵具体韵部名
        "东", "冬", "江", "支", "微", "鱼",
        # 词林正韵具体韵部
        "第一部", "第三部", "第七部",
    ]
    await probe_dimension("韵部", rhymes, "rhyme")

    # ============================================================
    # 维度 3: 风格 (style)
    # ============================================================
    styles = [
        "清新", "沉郁", "豪放", "婉约", "典雅",
        "朦胧", "狂野", "伤感", "悲壮", "空灵",
        "朴素", "华丽", "诙谐", "讽刺",
    ]
    await probe_dimension("风格", styles, "style")

    # ============================================================
    # 维度 4: 情感 (emotion)
    # ============================================================
    emotions = [
        "赞美", "感慨", "思念", "伤感", "讽刺",
        "忧虑", "闲适", "激昂", "喜悦", "思考",
        "悲愤", "惆怅", "豪迈", "恬淡", "哀愁",
    ]
    await probe_dimension("情感", emotions, "emotion")

    # ============================================================
    # 汇总
    # ============================================================
    print(f"\n\n{'='*60}")
    print("探测完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
