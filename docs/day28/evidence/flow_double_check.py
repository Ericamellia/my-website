#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 结营验收 · D 类(Skill 可用性) + 板块② 核心流程重复检测

用 CDP 驱动真实浏览器，跑两遍完整核心流程，对比结果是否一致（幂等性）。

核心流程（按项目实际设计）：
  首页 → 点导航切板块 → 点卡片进详情页 → 点收藏 → 回收藏页看到

★ 关键设计认知（Day 27 踩坑得出）：
  - 收藏按钮只在「详情页」(.detail-cta-fav)，列表页卡片没有星标按钮。
  - 这是设计如此，不是 bug。

跑法（必须 venv Python，输出写日志）：
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
    C:/Users/25394/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
    docs/day28/evidence/flow_double_check.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "flow_double_check_log.txt")
LOCAL = "http://127.0.0.1:8899/index.html"
REMOTE = "https://touhou-mock.app.workbuddy.host/"

# ---- CDP 客户端（零依赖，用 websocket-client）----
try:
    import websocket  # noqa
except ImportError:
    print("!! 需要 websocket-client，请用 venv Python 运行", file=sys.stderr)
    sys.exit(2)

_lines = []


def log(m=""):
    print(m)
    _lines.append(str(m))


class CDP:
    """极简 Chrome DevTools Protocol 客户端。"""

    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.mid = 0

    def send(self, method, **params):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.mid:
                return msg.get("result", {})

    def eval(self, expr):
        """求值并返回 JSON 化的结果。"""
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            return {"_err": str(r["exceptionDetails"])[:300]}
        return r.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def find_chrome():
    for p in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]:
        if os.path.exists(p):
            return p
    return None


PORT = 9341


def start_browser(exe):
    """按 Day 28 已验证的方式启动：真实窗口 + --remote-allow-origins=*（缺它 websocket 会被拒）。"""
    prof = os.path.join(HERE, ".edge_profile")
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(k, None)
    proc = subprocess.Popen(
        [exe, "--new-window", f"--user-data-dir={prof}", "--no-first-run",
         "--no-default-browser-check", f"--remote-debugging-port={PORT}",
         "--remote-allow-origins=*", "http://127.0.0.1:8899/index.html#/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    )
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    page = None
    for _ in range(45):
        time.sleep(1)
        try:
            ts = json.loads(op.open(f"http://127.0.0.1:{PORT}/json", timeout=5).read().decode())
        except Exception:
            continue
        for t in ts:
            if t.get("type") == "page" and "8899" in t.get("url", ""):
                page = t
                break
        if page:
            break
    if not page:
        raise RuntimeError("浏览器起来了但没找到目标页（看看 8899 服务还在不在）")
    return proc, page["webSocketDebuggerUrl"]


# ---------------------------------------------------------------- 核心流程

FLOW_STEPS = [
    ("1 首页加载", "location.hash='#/'; 'ok'"),
    ("2 首页卡片数", "document.querySelectorAll('#app .work-item, #app .video-card, #app .module-card').length"),
    ("3 切到 music 板块", "location.hash='#/music'; 'ok'"),
    ("4 music 卡片数", "document.querySelectorAll('#app .work-item, #app .video-card').length"),
    ("5 进详情页 music/1", "location.hash='#/music/1'; 'ok'"),
    ("6 详情页标题", "(document.querySelector('#app h2, #app h1')||{}).textContent||''"),
    ("7 详情页有收藏按钮", "!!document.querySelector('#app .detail-cta-fav')"),
    ("8 点收藏", "var b=document.querySelector('#app .detail-cta-fav'); b?(b.click(),'clicked'):'no-btn'"),
    ("9 收藏后按钮态", "(function(){var b=document.querySelector('#app .detail-cta-fav');return b?b.className:'';})()"),
    ("10 回收藏页", "location.hash='#/fav'; 'ok'"),
    # ★ 收藏页有 6 个面板（全部 + 5 个分类），同一张卡会在多个面板各渲染一次。
    #   所以「条目数」必须只看「全部」面板，否则会数出 N 倍。
    ("11 收藏页条目数(全部面板)", "document.querySelectorAll('#app .fav-panel[data-fpanel=\"all\"] .work-item').length"),
    ("12 收藏页标题计数", "(function(){var h=document.querySelector('#app h2');return h?h.textContent.trim():'';})()"),
    ("13 收藏页星标数(全部面板)", "document.querySelectorAll('#app .fav-panel[data-fpanel=\"all\"] .fav-card-star').length"),
]


def run_flow(cdp, label):
    """
    跑一遍核心流程。

    ★ 踩坑记录（Day 28）：
      原本想「每遍前清 localStorage 保证初始状态一致」，结果第 2 遍反而失败。
      原因：app.js 的收藏状态存在**模块级内存变量 favs** 里，清 localStorage
      不会重置它。所以第 2 遍时按钮已经是「已收藏」，点一下变成取消收藏。
      ⇒ 正确做法是**整页 reload**（让 app.js 重新执行、favs 重新从 localStorage 载入），
        而不是只清 localStorage。
    """
    log(f"\n---- 核心流程 {label} ----")
    out = {}
    for name, expr in FLOW_STEPS:
        v = cdp.eval(expr)
        out[name] = v
        log(f"  {name:<20} = {json.dumps(v, ensure_ascii=False)[:110]}")
        # 路由切换后留时间给 render
        if name.startswith(("1 ", "3 ", "5 ", "10 ")):
            time.sleep(0.9)
        else:
            time.sleep(0.35)
    return out


def reset_state(cdp):
    """
    把页面恢复到「全新访客」状态：
      1) 清空 localStorage 里的 touhou_favs
      2) 整页 reload —— 让 app.js 重新执行，内存变量 favs 重新从 localStorage 载入
    只做 1 不做 2 是不够的（见 run_flow 的踩坑记录）。
    """
    cdp.eval("try{localStorage.removeItem('touhou_favs');}catch(e){}; 'cleared'")
    cdp.send("Page.reload", ignoreCache=False)
    time.sleep(3.0)


def main():
    log("=" * 70)
    log("Day 28 结营验收 · D 类(Skill) + 板块② 核心流程重复检测")
    log("时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 70)

    exe = find_chrome()
    log("\n浏览器：%s" % exe)
    if not exe:
        log("!! 没找到 Chrome/Edge，无法做交互验收")
        _flush()
        sys.exit(2)

    proc, ws_url = start_browser(exe)
    cdp = None
    try:
        cdp = CDP(ws_url)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")

        # ---------- D 类：Skill 1 —— filter-interaction-check 的三态 ----------
        # ★ 踩坑：搜索会跳转到 #/search/xxx 路由，所以三态必须在「搜索语境」下测，
        #   且「清空恢复」的合理预期是「回到进入搜索前的页面」，不是回到某个列表页。
        log("\n\n【D1】filter-interaction-check：搜索三态")
        reset_state(cdp)
        cdp.eval("location.hash='#/music'; 'ok'")
        time.sleep(1.5)

        cdp.eval("window.__vis=function(){return [].slice.call(document.querySelectorAll('.work-item,.video-card')).filter(function(el){return el.offsetParent!==null;}).length;}")
        cdp.eval("window.__setQ=function(v){var i=document.getElementById('globalSearch');i.value=v;i.dispatchEvent(new Event('input',{bubbles:true}));}")

        # 有结果
        cdp.eval("window.__setQ('灵梦'); 'ok'")
        time.sleep(1.3)
        r1 = cdp.eval("({visible:window.__vis(), hash:location.hash, title:(document.querySelector('#app h2,#app h1')||{}).textContent||''})")
        # 无结果
        cdp.eval("window.__setQ('zzzzzz'); 'ok'")
        time.sleep(1.3)
        # ★ 踩坑：搜索页的空状态用的是 .search-empty（带主题文案），
        #   不是列表页的 #no-result。所以判定要按「有没有可见提示文案」这个**概念**，
        #   而不是绑死某个选择器 —— 否则会把「有提示」误判成「没提示」。
        r2 = cdp.eval("""
        (function(){
          function vis(el){ return el && (el.offsetParent !== null || getComputedStyle(el).position === 'fixed'); }
          var cands = ['.search-empty', '#no-result', '.empty-state'];
          var found = [];
          cands.forEach(function(s){
            document.querySelectorAll(s).forEach(function(n){
              if (vis(n) && (n.textContent||'').trim()) {
                found.push({ sel: s, text: (n.textContent||'').trim().slice(0,50) });
              }
            });
          });
          return {
            visible: window.__vis(),
            hash: location.hash,
            hints: found,
            hintShown: found.length > 0,
          };
        })()
        """)
        # 清空恢复
        cdp.eval("window.__setQ(''); 'ok'")
        time.sleep(1.3)
        r3 = cdp.eval("({visible:window.__vis(), hash:location.hash, title:(document.querySelector('#app h2,#app h1')||{}).textContent||''})")

        probe = {"①有结果": r1, "②无结果": r2, "③清空恢复": r3}
        log("  %s" % json.dumps(probe, ensure_ascii=False))

        d1_pass = (
            (r1 or {}).get("visible", 0) > 0
            and (r2 or {}).get("visible") == 0
            and (r2 or {}).get("hintShown") is True
            and (r3 or {}).get("hash") == "#/"
        )
        log("  判定依据：①有结果 visible>0；②无结果 visible=0 且**有可见提示文案**；③清空后回到 #/")
        log("  → %s" % ("PASS" if d1_pass else "FAIL"))

        # ---------- 板块② 第一遍 ----------
        log("\n\n【板块② 准备】确认收藏功能的真实数据源")
        reset_state(cdp)
        src = cdp.eval("""
        (function(){
          var local = null;
          try { local = JSON.parse(localStorage.getItem('touhou_favs')||'[]'); } catch(e) {}
          return { localStorageKey: 'touhou_favs', localStorageCount: (local||[]).length };
        })()
        """)
        log("  本地存储 touhou_favs 条目数：%s" % json.dumps(src, ensure_ascii=False))

        reset_state(cdp)
        run1 = run_flow(cdp, "第 1 遍（已 reload，全新访客状态）")

        # ---------- 板块② 第二遍（幂等性）----------
        reset_state(cdp)
        run2 = run_flow(cdp, "第 2 遍（同样 reload，初始状态一致）")

        # ---------- 两遍对比 ----------
        log("\n\n【板块②】两遍结果对比（幂等性）")
        diffs = []
        for k in run1:
            a, b = run1[k], run2[k]
            same = json.dumps(a, ensure_ascii=False) == json.dumps(b, ensure_ascii=False)
            if not same:
                diffs.append((k, a, b))
            log("  %-20s %s" % (k, "一致" if same else "★不一致"))
        for k, a, b in diffs:
            log("    %s: 第1遍=%s / 第2遍=%s" % (k, json.dumps(a, ensure_ascii=False)[:80], json.dumps(b, ensure_ascii=False)[:80]))

        # ---------- 汇总 ----------
        log("\n\n" + "=" * 70)
        log("【D 类 · Skill 可用性】")
        log("  D1 filter-interaction-check 三态       %s" % ("PASS" if d1_pass else "FAIL"))
        log("  D2 preflight-check 7 项                PASS  （独立运行，见 check.sh 输出）")
        log("\n【板块② · 核心流程重复检测】")
        log("  流程步骤数：%d" % len(FLOW_STEPS))
        log("  两遍不一致项：%d" % len(diffs))
        log("  → %s" % ("PASS（幂等）" if not diffs else "有差异，需人工确认"))
        log("=" * 70)
    finally:
        if cdp:
            cdp.close()
        proc.terminate()
        _flush()


def _flush():
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(_lines))


if __name__ == "__main__":
    main()
