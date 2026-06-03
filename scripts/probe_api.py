"""逐一探测 retrieve_poems 的参数可接受范围"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("POEM_ACCESS_TOKEN", "")

async def probe(body: dict, label: str):
    async with httpx.AsyncClient(base_url="https://poem.pkudh.org", timeout=30) as c:
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Origin": "https://poem.pkudh.org",
            "Referer": "https://poem.pkudh.org/",
            "User-Agent": "Mozilla/5.0",
        }
        r = await c.post("/poems/retrieve_poems", json=body, headers=headers)
        status = r.status_code
        text = r.text[:200]
        return status, text

async def main():
    base = {"query": "春天", "form": "五律", "yan": 5, "rhyme": "平水", "genre": "清"}
    
    tests = [
        ("基线", base),
        ("query=静夜思", {**base, "query": "静夜思"}),
        ("form=律诗", {**base, "form": "律诗"}),
        ("form=绝句", {**base, "form": "绝句"}),
        ("form=古风", {**base, "form": "古风"}),
        ("yan=7", {**base, "yan": 7}),
        ("genre=淡", {**base, "genre": "淡"}),
        ("rhyme=词林", {**base, "rhyme": "词林"}),
        ("rhyme=平", {**base, "rhyme": "平"}),
        ("最小请求", {"query":"春","form":"五律","yan":5,"rhyme":"平水","genre":"清"}),
    ]
    
    for label, body in tests:
        status, text = await probe(body, label)
        print(f"[{status}] {label}: {text}")

asyncio.run(main())
