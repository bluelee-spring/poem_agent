"""测试不带 token 和假 token 的 API 响应"""
import asyncio
import httpx

async def test():
    body = {"query": "春天", "form": "五律", "yan": 5, "rhyme": "平水", "genre": "清"}
    
    async with httpx.AsyncClient(base_url="https://poem.pkudh.org", timeout=30) as c:
        # 1. 无 token
        r = await c.post("/poems/retrieve_poems", json=body)
        print(f"无 token: {r.status_code} {r.text[:300]}")
        
        # 2. 假 token
        r2 = await c.post("/poems/retrieve_poems", json=body,
                          headers={"Authorization": "Bearer fake123"})
        print(f"假 token: {r2.status_code} {r2.text[:300]}")
        
        # 3. 不带 body
        r3 = await c.post("/poems/retrieve_poems")
        print(f"无 body: {r3.status_code} {r3.text[:300]}")

asyncio.run(test())
