#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 · 铁证：点「收藏」到底发不发 HTTP 请求

用 CDP 的 Network domain 全程抓包，统计点击收藏按钮前后的网络请求。
如果点击期间**没有任何写请求**（POST/PATCH/DELETE /api/favorites），
就证明收藏完全是本地 localStorage 行为，与真库脱钩。

同时对比：手动 fetch('/api/favorites') 时是**有**请求的 —— 作为对照组，
证明抓包本身是有效的（不是因为抓包失灵才「没请求」）。
"""
import json
import os
import subprocess
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "net_proof_log.txt")
PORT = 9343

_lines = []


def log(m=""):
    print(m)
    _lines.append(str(m))


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.mid = 0
        self.events = []

    def send(self, method, **params):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.mid:
                return m.get("result", {})
            if "method" in m:
                self.events.append(m)

    def drain(self, sec=1.0):
        """收一段时间的事件（不阻塞太久）。"""
        end = time.time() + sec
        self.ws.settimeout(0.3)
        while time.time() < end:
            try:
                m = json.loads(self.ws.recv())
                if "method" in m:
                    self.events.append(m)
            except Exception:
                pass
        self.ws.settimeout(30)

    def ev(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            return {"_err": str(r["exceptionDetails"])[:200]}
        return r.get("result", {}).get("value")

    def requests(self):
        out = []
        for e in self.events:
            if e.get("method") == "Network.requestWillBeSent":
                p = e["params"]
                out.append({"method": p.get("request", {}).get("method"),
                            "url": p.get("request", {}).get("url", "")})
        return out


def main():
    log("=" * 74)
    log("铁证：点「收藏」按钮期间有没有发写请求")
    log("=" * 74)

    exe = None
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p):
            exe = p
            break

    prof = os.path.join(HERE, ".edge_net")
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(k, None)

    proc = subprocess.Popen(
        [exe, "--new-window", f"--user-data-dir={prof}", "--no-first-run",
         "--no-default-browser-check", f"--remote-debugging-port={PORT}",
         "--remote-allow-origins=*", "http://127.0.0.1:8899/index.html#/music/1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

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

    cdp = CDP(page["webSocketDebuggerUrl"])
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    cdp.send("Network.enable")
    time.sleep(3.5)

    try:
        log("\n【准备】打开详情页 #/music/1，已开 Network 抓包")
        log("  按钮存在：%s" % cdp.ev("!!document.querySelector('#app .detail-cta-fav')"))

        # ---- 测试组：点收藏按钮，看有没有请求 ----
        cdp.events.clear()
        log("\n【测试组】点击「收藏」按钮（.detail-cta-fav）")
        log("  点击：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');if(!b)return 'no-btn';b.click();return 'clicked';})()"))
        cdp.drain(2.5)
        reqs = cdp.requests()
        writes = [r for r in reqs if r["method"] in ("POST", "PATCH", "DELETE", "PUT")]
        fav_writes = [r for r in writes if "/api/favorites" in r["url"]]
        log("  这段时间的请求总数：%d" % len(reqs))
        for r in reqs[:12]:
            log("    %-7s %s" % (r["method"], r["url"][:100]))
        log("  写请求（POST/PATCH/DELETE/PUT）数：%d" % len(writes))
        log("  针对 /api/favorites 的写请求数：%d" % len(fav_writes))
        test_pass = len(fav_writes) == 0
        log("  → 点收藏%s发出写请求  %s" % ("没有" if test_pass else "★发出了", "PASS（确认为纯本地）" if test_pass else "FAIL"))

        # ---- 对照组：手动 fetch 一次，证明抓包有效 ----
        cdp.events.clear()
        log("\n【对照组】手动 fetch('/api/favorites?limit=1')，验证抓包确实能抓到")
        cdp.ev("fetch('/api/favorites?limit=1').then(r=>r.status)")
        cdp.drain(2.5)
        reqs2 = cdp.requests()
        api_reqs = [r for r in reqs2 if "/api/favorites" in r["url"]]
        log("  抓到的 /api/favorites 请求数：%d" % len(api_reqs))
        for r in api_reqs:
            log("    %-7s %s" % (r["method"], r["url"][:100]))
        ctrl_pass = len(api_reqs) > 0
        log("  → 抓包有效？%s" % ("是（PASS）" if ctrl_pass else "★否（抓包可能失灵，需重做）"))

        log("\n" + "=" * 74)
        log("【结论】")
        log("  测试组：点收藏按钮 → /api/favorites 写请求 %d 个" % len(fav_writes))
        log("  对照组：手动 fetch      → /api/favorites 请求 %d 个" % len(api_reqs))
        if test_pass and ctrl_pass:
            log("  → 确证：页面「收藏」按钮不写库，是纯 localStorage 本地行为；")
            log("          而真库 /api/favorites 通道本身是通的（对照组抓到了）。")
            log("          ⇒ 前端收藏 UI 与云端真库「两套数据、互不相通」。")
        else:
            log("  → 结论不成立，需要重新设计验证。")
        log("=" * 74)
    finally:
        try:
            cdp.ws.close()
        except Exception:
            pass
        proc.terminate()
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(_lines))


if __name__ == "__main__":
    main()
