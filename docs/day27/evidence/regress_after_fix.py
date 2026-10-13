# Day 27 修复后回归：直接打公网接口，确认修复没改坏别的
#
# 为什么打公网而不是本地：改的是数据层 mapper，只有接真库才能验证；
# 本地没凭据会降级到快照通道，测不出真库路径。
import json
import os
import urllib.error
import urllib.request

SITE = "https://touhou-mock.app.workbuddy.host"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)

passed = 0
failed = 0


def get(path, expect=200, timeout=20):
    req = urllib.request.Request(SITE + path, headers={"User-Agent": "regress/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, None


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  [PASS] %s" % name)
    else:
        failed += 1
        print("  [FAIL] %s  %s" % (name, detail))


print("=" * 66)
print("Day 27 修复后回归（公网真实环境）")
print("=" * 66)
print()

# ── A. 只读接口冒烟 ──────────────────────────────
print("A. 只读接口冒烟")
for path, label in [
    ("/api/health", "健康检查"),
    ("/api/hot", "热搜榜"),
    ("/api/favorites?userId=local", "收藏列表"),
    ("/api/circles", "社团列表"),
    ("/api/characters", "角色列表"),
    ("/api/original-games", "原作游戏"),
    ("/api/originals", "原曲"),
]:
    code, d = get(path)
    ok = code == 200 and (d or {}).get("ok") is True
    check("%s  %s" % (label, path), ok, "code=%s" % code)
print()

# ── B. 五板块都能拿到，且社团不为空（本次修复核心） ──
print("B. 五板块作品 + 社团字段（本次修复核心）")
all_ok = True
for c in ["music", "doujin", "game", "video", "art"]:
    code, d = get("/api/works?category=%s&limit=200" % c)
    items = (d or {}).get("data") or []
    has_circle = sum(1 for w in items if w.get("circle"))
    n = len(items)
    ok = code == 200 and n > 0 and has_circle == n
    check("%-8s %d 件，社团有值 %d 件" % (c, n, has_circle), ok,
          "code=%s 有值=%d/%d" % (code, has_circle, n))
    all_ok = all_ok and ok
print()

# ── C. 字段完整性（原来缺的字段现在都在） ──
print("C. 作品字段完整性（music 抽样）")
code, d = get("/api/works?category=music&limit=1")
w = ((d or {}).get("data") or [{}])[0]
for field, label in [
    ("id", "板块内数字 id"), ("workId", "原串 workId"),
    ("name", "作品名"), ("circle", "社团（本次修复）"),
    ("creator", "创作者"), ("year", "年份"), ("cover", "封面"),
]:
    v = w.get(field)
    check("%-14s = %s" % (label, repr(v)[:40]), v is not None and v != "")
print()

# ── D. 错误路径仍然规范（修复不该影响错误处理） ──
print("D. 错误路径（不该泄漏内部细节）")
code, d = get("/api/works?category=%E4%B8%8D%E5%AD%98%E5%9C%A8")  # URL 编码的「不存在」
check("非法 category → 400", code == 400, "code=%s" % code)
check("  返回了合法值列表", bool((d or {}).get("valid")), str(d)[:80])
msg = json.dumps(d or {}, ensure_ascii=False)
check("  没泄漏内部堆栈/连接串",
      ("at " not in msg and "postgres" not in msg.lower() and "stack" not in msg.lower()))
print()

# ── E. 收藏接口未受影响 ──
print("E. 收藏接口（确认修复没改坏它）")
code, d = get("/api/favorites?userId=local")
items = (d or {}).get("data") or []
check("收藏列表可读，%d 条" % len(items), code == 200 and len(items) > 0)
if items:
    with_circle = sum(1 for f in items if f.get("circle"))
    check("  收藏条目的 circle 有值 %d/%d" % (with_circle, len(items)), with_circle == len(items))
    check("  作品名不是「(作品已下架)」",
          all(f.get("name") != "(作品已下架)" for f in items))
print()

print("=" * 66)
print("汇总：通过 %d 项，失败 %d 项" % (passed, failed))
print("=" * 66)
