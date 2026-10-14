#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 · 诊断：收藏按钮点击前后的真实状态

目的：搞清楚第 1 遍 / 第 2 遍结果不同的**根因**，
      判断是产品 bug 还是我的测试脚本设计缺陷。

做法：不预设结论，逐步打印「点击前后」的收藏总数（直接调 /api/favorites），
      对比前端按钮 class，找出到底发生了什么。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "diag_fav_log.txt")
SITE = "https://touhou-mock.app.workbuddy.host"
PORT = 9342

_lines = []


def log(m=""):
    print(m)
    _lines.append(str(m))


def api_count():
    """直接查公网真库的收藏总数（绕代理）。"""
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        d = json.loads(op.open(SITE + "/api/favorites?limit=50", timeout=15).read().decode())
        return d.get("count"), [x.get("workId") for x in d.get("data", [])]
    except Exception as e:
        return None, [repr(e)]


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=30)
        self.mid = 0

    def send(self, method, **p):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": p}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.mid:
                return m.get("result", {})

    def ev(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            return {"_err": str(r["exceptionDetails"])[:200]}
        return r.get("result", {}).get("value")


def main():
    log("=" * 70)
    log("诊断：收藏按钮点击前后的真实状态")
    log("=" * 70)

    exe = None
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"]:
        if os.path.exists(p):
            exe = p
            break
    log("浏览器：%s" % exe)

    prof = os.path.join(HERE, ".edge_diag")
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
    time.sleep(3.5)

    try:
        c = ids = None
        c, ids = api_count()
        log("\n【起点】公网收藏 count=%s" % c)
        log("  含 music-1 吗？%s" % ("是" if ids and "music-1" in ids else "否"))

        log("\n【详情页状态】当前在 #/music/1")
        log("  按钮存在：%s" % cdp.ev("!!document.querySelector('#app .detail-cta-fav')"))
        log("  按钮 class：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');return b?b.className:'(无)';})()"))
        log("  按钮文案：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');return b?b.textContent.trim():'(无)';})()"))

        log("\n【第 1 次点击收藏按钮】")
        log("  点击结果：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');if(!b)return 'no-btn';b.click();return 'clicked';})()"))
        time.sleep(2.5)
        c2, ids2 = api_count()
        log("  点击后 → 公网 count=%s（含 music-1？%s）" % (c2, "是" if ids2 and "music-1" in ids2 else "否"))
        log("  按钮 class：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');return b?b.className:'(无)';})()"))
        log("  按钮文案：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');return b?b.textContent.trim():'(无)';})()"))

        log("\n【第 2 次点击同一个按钮】")
        log("  点击结果：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');if(!b)return 'no-btn';b.click();return 'clicked';})()"))
        time.sleep(2.5)
        c3, ids3 = api_count()
        log("  点击后 → 公网 count=%s（含 music-1？%s）" % (c3, "是" if ids3 and "music-1" in ids3 else "否"))
        log("  按钮 class：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');return b?b.className:'(无)';})()"))
        log("  按钮文案：%s" % cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');return b?b.textContent.trim():'(无)';})()"))

        log("\n【结论】")
        log("  起点 count=%s → 第1次点后 %s → 第2次点后 %s" % (c, c2, c3))
        if c2 == (c or 0) - 1:
            log("  → 第 1 次点击是「取消收藏」（count -1）")
        elif c2 == (c or 0) + 1:
            log("  → 第 1 次点击是「新增收藏」（count +1）")
        else:
            log("  → count 未按预期变化，需细看")
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
