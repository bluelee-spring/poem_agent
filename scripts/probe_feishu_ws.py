"""探测飞书 Wiki API — 验证 token → obj_token 链路"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
WIKI_TOKEN = "OofGwwSuRiDblfksV9kc2XadnJc"
TABLE_ID = "tblSgghJkzr7Vz3A"

async def probe():
    if not APP_ID or not APP_SECRET:
        print("[FAIL] 未配置 FEISHU_APP_ID / FEISHU_APP_SECRET")
        return

    async with httpx.AsyncClient(timeout=15) as c:
        # Step 1: 获取 tenant_access_token
        print("[1] 获取 tenant_access_token...")
        r = await c.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET},
        )
        if r.status_code != 200:
            print(f"[FAIL] token 获取失败: {r.status_code} {r.text[:200]}")
            return
        token_data = r.json()
        access_token = token_data["tenant_access_token"]
        print(f"[OK] token 获取成功")

        # Step 2: 通过 Wiki token 获取节点信息
        print(f"\n[2] 获取 Wiki 节点信息 (token={WIKI_TOKEN[:20]}...)...")
        r = await c.get(
            f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node",
            params={"token": WIKI_TOKEN},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code != 200:
            print(f"[FAIL] Wiki API: {r.status_code} {r.text[:300]}")
            return
        node = r.json()
        print(f"[OK] Wiki API 返回:")
        print(f"  node.obj_type: {node.get('data',{}).get('node',{}).get('obj_type','?')}")
        print(f"  node.obj_token: {node.get('data',{}).get('node',{}).get('obj_token','?')}")
        print(f"  node.title: {node.get('data',{}).get('node',{}).get('title','?')}")
        obj_token = node.get("data", {}).get("node", {}).get("obj_token", "")

        if not obj_token:
            print("[FAIL] 未获取到 obj_token，完整响应:")
            print(r.text[:500])
            return

        # Step 3: 尝试列出 Bitable 表字段
        print(f"\n[3] 获取 Bitable 表字段 (app_token={obj_token[:20]}..., table={TABLE_ID})...")
        r = await c.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{obj_token}/tables/{TABLE_ID}/fields",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code != 200:
            print(f"[FAIL] Bitable API: {r.status_code} {r.text[:300]}")
            return
        fields_data = r.json()
        print(f"[OK] Bitable 表字段:")
        items = fields_data.get("data", {}).get("items", [])
        for f in items:
            print(f"  - {f.get('field_name','?')} ({f.get('type','?')})")
        print(f"  共 {len(items)} 个字段")

        # Step 4: 尝试写入一条测试记录
        if items:
            print(f"\n[4] 写入测试记录...")
            test_fields = {}
            for f in items:
                name = f.get("field_name", "")
                ftype = f.get("type", 1)
                if ftype == 1:  # 文本
                    test_fields[name] = f"[测试] {name}"
            r = await c.post(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{obj_token}/tables/{TABLE_ID}/records",
                json={"fields": test_fields},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 200:
                print(f"[OK] 写入成功！record_id: {r.json().get('data',{}).get('record',{}).get('record_id','?')}")
            else:
                print(f"[FAIL] 写入失败: {r.status_code} {r.text[:300]}")

asyncio.run(probe())
