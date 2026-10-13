# Day 27 试用：扫描所有板块的「字段缺失」情况
#
# 用来判断「同人音乐社团全空」是个例还是普遍问题。
import json
import os
import urllib.request

SITE = "https://touhou-mock.app.workbuddy.host"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)

CATS = ["music", "doujin", "game", "video", "art"]


def get(path):
    req = urllib.request.Request(SITE + path, headers={"User-Agent": "trial/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


print("=" * 70)
print("各板块字段完整性扫描")
print("=" * 70)
print()
print("%-10s %5s %8s %8s %8s %8s" % ("板块", "总数", "社团空", "年份空", "封面空", "名称空"))
print("-" * 70)

total_all = 0
miss_circle_all = 0
for c in CATS:
    try:
        d = get("/api/works?category=%s&limit=200" % c)
        items = d.get("data") or []
    except Exception as e:
        print("%-10s  请求失败: %s" % (c, e))
        continue
    n = len(items)
    # ★ Day 27：接口对外字段名是 circle（不是 circle_name），
    #   下面这几个统计都按对外字段名来。
    mc = sum(1 for w in items if not w.get("circle"))
    my = sum(1 for w in items if not w.get("year"))
    mv = sum(1 for w in items if not w.get("cover"))
    mn = sum(1 for w in items if not w.get("name"))
    total_all += n
    miss_circle_all += mc
    print("%-10s %5d %8d %8d %8d %8d" % (c, n, mc, my, mv, mn))

print("-" * 70)
print("合计 %d 件，其中社团名为空 %d 件" % (total_all, miss_circle_all))
print()

# 详细看 music 板块一条记录的原始字段
print("=" * 70)
print("样本：同人音乐第一条的完整字段")
print("=" * 70)
d = get("/api/works?category=music&limit=200")
if d.get("data"):
    w = d["data"][0]
    for k in sorted(w.keys()):
        v = w[k]
        sv = str(v)
        print("  %-14s = %s" % (k, sv[:70] if sv else "(空)"))
