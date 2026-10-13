# Day 27 资源额度检查：采集可观测的用量指标
#
# 说明：真实额度（配额上限、到期日）在云开发控制台，脚本拿不到。
# 这里采集的是「运行时可观测用量」，作为额度检查的可验证部分，
# 并给出控制台查看路径供人工核对。
import json
import os
import time
import urllib.request

SITE = "https://touhou-mock.app.workbuddy.host"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)


def get(path):
    req = urllib.request.Request(SITE + path, headers={"User-Agent": "quota/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


print("=" * 66)
print("资源额度检查")
print("时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 66)
print()

# ── 1. 服务健康与版本 ──
print("【1】服务健康")
code, h = get("/api/health")
print("  HTTP %s" % code)
print("  服务名    : %s" % h.get("service"))
print("  环境      : %s" % h.get("env"))
print("  版本      : %s" % h.get("version"))
print("  Node      : %s" % h.get("node"))
print("  已运行    : %d 秒（约 %.1f 小时）" % (h.get("uptimeSec", 0), h.get("uptimeSec", 0) / 3600))
print("  数据通道  : %s" % h.get("checks", {}).get("dataSource"))
print()

# ── 2. 数据用量（接口可见的部分） ──
print("【2】数据用量（当前线上数据）")
total_rows = 0
for path, label in [
    ("/api/works?limit=500", "works 作品"),
    ("/api/circles", "circles 社团"),
    ("/api/characters", "characters 角色"),
    ("/api/original-games", "original_games 原作"),
    ("/api/originals", "originals 原曲"),
    ("/api/hot", "hot 热搜"),
    ("/api/favorites?userId=local", "favorites 收藏"),
]:
    try:
        code, d = get(path)
        items = d.get("data")
        if isinstance(items, dict):
            n = sum(len(v) for v in items.values() if isinstance(v, list))
        elif isinstance(items, list):
            n = len(items)
        else:
            n = 0
        total_rows += n
        print("  %-22s %4d 条   (HTTP %s)" % (label, n, code))
    except Exception as e:
        print("  %-22s  查询失败: %s" % (label, e))
print("  %-22s %4d 条" % ("合计", total_rows))
print()

# ── 3. 静态资源体积（从本地部署目录算，线上一致） ──
print("【3】静态资源体积（部署包）")
root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), "deploy")
total_bytes = 0
file_count = 0
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d != "node_modules"]
    for f in fn:
        fp = os.path.join(dp, f)
        try:
            total_bytes += os.path.getsize(fp)
            file_count += 1
        except Exception:
            pass
print("  文件数    : %d 个（不含 node_modules）" % file_count)
print("  总体积    : %.1f MB" % (total_bytes / 1024 / 1024))
print()

# ── 4. 接口响应耗时（性能额度参考） ──
print("【4】接口响应耗时抽样（各 3 次取平均）")
for path, label in [("/api/health", "health"), ("/api/works?category=music&limit=200", "works"),
                    ("/api/hot", "hot"), ("/api/favorites?userId=local", "favorites")]:
    ts = []
    for _ in range(3):
        t0 = time.time()
        try:
            get(path)
            ts.append(time.time() - t0)
        except Exception:
            pass
    if ts:
        print("  %-12s 平均 %.0f ms" % (label, sum(ts) / len(ts) * 1000))
print()

print("=" * 66)
print("人工核对项（需在控制台查看，脚本无法获取）")
print("=" * 66)
print("  ① CloudBase 环境：配额上限 / 已用量 / 到期日")
print("     → https://console.cloud.tencent.com/tcb  选对应环境 → 用量/资源")
print("  ② WorkBuddy 发布额度")
print("     → 「设置 — 数据管理 — 应用」查看已发布应用")
print("  ③ 域名证书有效期（HTTPS）")
print("     → 发布平台自动管理，控制台可见")
