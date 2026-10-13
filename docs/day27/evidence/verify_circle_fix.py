# Day 27 验证：本地起服务，确认 circle 字段修复生效
#
# 为什么在本地起服务测：改的是 deploy/ 里的代码，直接测本地就能验证，
# 不用先发布到公网（发布前验证，符合发布清单的要求）。
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEPLOY = os.path.join(ROOT, "deploy")
PORT = 3731

# 清代理
env = dict(os.environ)
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    env.pop(k, None)
env["PORT"] = str(PORT)

print("启动本地服务：%s（PORT=%d）" % (DEPLOY, PORT))
proc = subprocess.Popen(
    ["node", "server.js"],
    cwd=DEPLOY, env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)

BASE = "http://127.0.0.1:%d" % PORT


def get(path, timeout=15):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


try:
    # 等服务起来
    ok = False
    for _ in range(40):
        time.sleep(0.5)
        try:
            h = get("/api/health")
            if h.get("ok"):
                ok = True
                break
        except Exception:
            pass
    if not ok:
        print("✗ 本地服务没起来")
        proc.kill()
        out = proc.stdout.read().decode("utf-8", "ignore")
        print(out[:2000])
        sys.exit(1)

    print("✓ 本地服务已就绪\n")
    print("=" * 64)
    print("修复验证：各板块 circle（社团）字段")
    print("=" * 64)
    print("%-10s %6s %8s %10s" % ("板块", "总数", "社团有值", "社团为空"))
    print("-" * 64)

    total = 0
    filled = 0
    for c in ["music", "doujin", "game", "video", "art"]:
        d = get("/api/works?category=%s&limit=200" % c)
        items = d.get("data") or []
        n = len(items)
        has = sum(1 for w in items if w.get("circle"))
        empty = n - has
        total += n
        filled += has
        print("%-10s %6d %8d %10d" % (c, n, has, empty))

    print("-" * 64)
    print("合计 %d 件，社团有值 %d 件，为空 %d 件" % (total, filled, total - filled))
    print()

    # 抽样看看具体值
    print("抽样（同人音乐前 3 件）：")
    d = get("/api/works?category=music&limit=200")
    for w in (d.get("data") or [])[:3]:
        print("  %-28s 社团=%s" % ((w.get("name") or "")[:26], w.get("circle") or "(空!)"))
    print()

    # 顺带确认收藏接口没被改坏
    print("回归：收藏接口 circle 仍正常？")
    d = get("/api/favorites?userId=local")
    it = d.get("data") or []
    print("  收藏 %d 条，第一条 club=%s" % (len(it), (it[0].get("circle") if it else "(无)")))
    print()

    if filled == total and total > 0:
        print(">>> ✅ 修复生效：全部 %d 件作品的社团都有值" % total)
    else:
        print(">>> ❌ 仍有 %d 件社团为空" % (total - filled))

finally:
    proc.kill()
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    print("\n本地服务已关闭")
