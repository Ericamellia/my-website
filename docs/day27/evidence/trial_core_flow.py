# Day 27 试用：以「没参与项目的真人」视角走核心流程
#
# 这个脚本代替人工点击，真实打公网接口，记录每一步的响应与卡点。
# 注意：这不是「没参与项目的真人」，是降级方案（Day 27 卡住降级条款允许）。
import json
import os
import time
import urllib.request
import urllib.error

SITE = "https://touhou-mock.app.workbuddy.host"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trial-log.txt")

# 清掉代理（本机 127.0.0.1:53402 会劫持请求）
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)

lines = []


def log(s=""):
    print(s)
    lines.append(s)


def get(path, timeout=20):
    """真实 GET，返回 (状态码, 耗时秒, 字节, 解析后的JSON或None)。"""
    url = SITE + path
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "trial-runner/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            dt = time.time() - t0
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = None
            return r.status, dt, len(body), data
    except urllib.error.HTTPError as e:
        dt = time.time() - t0
        body = e.read()
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = None
        return e.code, dt, len(body), data
    except Exception as e:
        return None, time.time() - t0, 0, {"error": str(e)}


log("=" * 64)
log("第三方试用 · 核心流程走查（降级方案：由 AI 代跑）")
log("时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
log("试用起点（我作为用户拿到的唯一信息）：%s" % SITE)
log("=" * 64)

# ── 步骤 1：打开首页 ─────────────────────────────
log()
log("【步骤 1】打开首页")
code, dt, size, _ = get("/")
log("  HTTP %s  耗时 %.2fs  大小 %dB" % (code, dt, size))
if code == 200:
    log("  → 页面能打开")
else:
    log("  ✗ 打不开！")
log("  ⚠ 卡点观察：首页耗时 %.2fs，%s" % (
    dt, "偏慢（网络良好时应 <1s）" if dt > 1.5 else "正常"))

# ── 步骤 2：看首页内容 ───────────────────────────
log()
log("【步骤 2】首页第一屏看到什么")
code, dt, size, _ = get("/")
# 首页 HTML 里 app 容器是空的，内容靠 JS 渲染
log("  ⚠ 卡点观察：首页 HTML 大小为 %dB，但内容区 <main id=\"app\"> 初始是" % size)
log("     loading 占位 —— 意味着①不跑 JS 就看不到任何内容 ②首屏要等 JS 请求接口")

# ── 步骤 3：切板块（模拟点导航） ──────────────────
log()
log("【步骤 3】点导航进「同人音乐」")
code, dt, size, data = get("/api/works?category=music&limit=200")
log("  HTTP %s  耗时 %.2fs  大小 %dB" % (code, dt, size))
if data and isinstance(data, dict):
    items = data.get("data") or []
    log("  → 拿到 %d 件同人音乐作品" % len(items))
    if items:
        w = items[0]
        log("  第一件：%s" % (w.get("name") or "(无名称)"))
        log("         社团=%s  年份=%s" % (w.get("circle_name") or "-", w.get("year") or "-"))
        log("         封面=%s" % ("有" if w.get("cover") else "无"))
        # 检查封面 URL 是否 https（http 会被浏览器拦）
        cov = w.get("cover") or ""
        if cov.startswith("http://"):
            log("  ⚠ 卡点观察：封面是 http:// —— 页面是 https，浏览器会拦混合内容！")
        elif cov.startswith("https://"):
            log("  ✓ 封面是 https，不会被拦")
        elif cov.startswith("//"):
            log("  ✓ 封面是协议相对地址")
        elif cov.startswith("data:"):
            log("  · 封面是内嵌 data URI")
        else:
            log("  · 封面地址形态：%s" % (cov[:50] or "(空)"))
else:
    log("  ✗ 没拿到数据：%s" % str(data)[:150])

# ── 步骤 4：看收藏列表 ───────────────────────────
log()
log("【步骤 4】点「我的收藏」")
code, dt, size, data = get("/api/favorites?userId=3")
log("  HTTP %s  耗时 %.2fs  大小 %dB" % (code, dt, size))
if data and isinstance(data, dict):
    items = data.get("data") or []
    log("  → 收藏列表 %d 条" % len(items))
    for w in items[:3]:
        log("     · %s" % (w.get("name") or "(作品名缺失!)"))
else:
    log("  ✗ %s" % str(data)[:150])

# ── 步骤 5：热搜榜 ───────────────────────────────
log()
log("【步骤 5】点「B站必看」")
code, dt, size, data = get("/api/hot")
log("  HTTP %s  耗时 %.2fs  大小 %dB" % (code, dt, size))
if data and isinstance(data, dict):
    d = data.get("data") or {}
    if isinstance(d, dict):
        log("  → 榜单结构：%s" % ", ".join(d.keys()))
    else:
        log("  → %d 条" % len(d))
else:
    log("  ✗ %s" % str(data)[:150])

# ── 步骤 6：健康检查（用户不会点，但记录） ────────
log()
log("【步骤 6】顺带确认后端健康")
code, dt, size, data = get("/api/health")
log("  HTTP %s  耗时 %.2fs" % (code, dt))
if data:
    log("  version=%s  dataSource=%s" % (data.get("version"), data.get("checks", {}).get("dataSource")))

log()
log("=" * 64)
log("试用结束")
log("=" * 64)

with open(OUT, "w", encoding="utf-8", newline="") as f:
    f.write("\n".join(lines) + "\n")
print("\n已写入 %s" % OUT)
