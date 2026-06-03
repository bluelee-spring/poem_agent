"""API 连通性测试脚本"""
import ssl, urllib.request, json, sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 测试1: OAuth 登录 URL
print("=== 测试1: GET /oauth/login?debug=true ===")
try:
    url = "https://poem.pkudh.org/oauth/login?debug=true"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        data = json.loads(resp.read().decode())
        print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"失败 ({type(e).__name__}): {e}")

# 测试2: 无认证访问 check-login（预期返回 401）
print("\n=== 测试2: GET /oauth/check-login (无 token)===")
try:
    url = "https://poem.pkudh.org/oauth/check-login"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        print(f"状态: {resp.status}")
        print(resp.read().decode()[:500])
except urllib.error.HTTPError as e:
    print(f"预期中的 HTTP 错误: {e.code} - {e.reason}")
    print(e.read().decode()[:500])
except Exception as e:
    print(f"失败 ({type(e).__name__}): {e}")
