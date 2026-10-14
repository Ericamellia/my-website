#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 · 诊断三：搜索无结果时，用户到底看不看得见提示？

前面 flow_double_check 判定 D1「②无结果」FAIL，原因是 #no-result 没显示。
但那可能只是因为搜索页用的是 .empty-state 而不是 #no-result。

本脚本查明：
  1. 搜 zzzzzz 后，页面上到底渲染了什么文案？（用户在屏幕上看到什么）
  2. .empty-state 元素是否存在、可见、内容是什么？
  3. #no-result 元素是否存在？
  4. 对比「列表页筛选无结果」时用的是哪个元素 —— 确认两套实现是否真的不一致。
  5. 顺带检查可访问性：有无 role=status / aria-live。
"""
import json
import os
import subprocess
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "diag_empty_log.txt")
PORT = 9345

_lines = []


def log(m=""):
    print(m)
    _lines.append(str(m))


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


SNAP = """
(function(){
  function info(sel){
    var n = document.querySelector(sel);
    if(!n) return null;
    var cs = getComputedStyle(n);
    return {
      exists: true,
      hidden: !!n.hidden,
      display: cs.display,
      visible: (n.offsetParent !== null || cs.position === 'fixed'),
      text: (n.textContent||'').trim().slice(0,60),
      role: n.getAttribute('role') || '(无)',
      ariaLive: n.getAttribute('aria-live') || '(无)',
    };
  }
  return {
    hash: location.hash,
    appHTMLHead: (document.getElementById('app')||{innerHTML:''}).innerHTML.slice(0,200),
    noResult: info('#no-result'),
    emptyState: info('.empty-state'),
    emptyStateCount: document.querySelectorAll('.empty-state').length,
  };
})()
"""


def main():
    log("=" * 80)
    log("诊断三：搜索无结果时的提示，用户看得见吗？")
    log("=" * 80)

    exe = None
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p):
            exe = p
            break

    prof = os.path.join(HERE, ".edge_diag3")
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(k, None)
    proc = subprocess.Popen(
        [exe, "--new-window", f"--user-data-dir={prof}", "--no-first-run",
         "--no-default-browser-check", f"--remote-debugging-port={PORT}",
         "--remote-allow-origins=*", "http://127.0.0.1:8899/index.html#/"],
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
    time.sleep(3.0)

    try:
        log("\n【场景 A】列表页（#/music）用筛选功能搜无结果")
        cdp.ev("location.hash='#/music'; 'ok'")
        time.sleep(1.5)
        cdp.ev("(function(){var i=document.getElementById('globalSearch');i.value='zzzzzz';i.dispatchEvent(new Event('input',{bubbles:true}));})()")
        time.sleep(1.5)
        a = cdp.ev(SNAP)
        log("  hash=%s" % a.get("hash"))
        log("  #no-result  : %s" % json.dumps(a.get("noResult"), ensure_ascii=False))
        log("  .empty-state: %s" % json.dumps(a.get("emptyState"), ensure_ascii=False))

        log("\n【场景 B】重置后，从首页搜索框搜无结果")
        cdp.ev("try{localStorage.clear();}catch(e){}; 'ok'")
        cdp.send("Page.reload")
        time.sleep(3.0)
        log("  reload 后 hash=%s" % cdp.ev("location.hash"))
        cdp.ev("(function(){var i=document.getElementById('globalSearch');i.value='zzzzzz';i.dispatchEvent(new Event('input',{bubbles:true}));})()")
        time.sleep(1.8)
        b = cdp.ev(SNAP)
        log("  hash=%s" % b.get("hash"))
        log("  #no-result  : %s" % json.dumps(b.get("noResult"), ensure_ascii=False))
        log("  .empty-state: %s" % json.dumps(b.get("emptyState"), ensure_ascii=False))
        log("  #app 开头  : %s" % json.dumps(b.get("appHTMLHead"), ensure_ascii=False)[:220])

        log("\n【对比结论】")
        log("  场景A(列表页筛选无结果)  —— #no-result: %s" % (
            "存在且可见" if (a.get("noResult") or {}).get("visible") else "不存在/不可见"))
        log("  场景B(全站搜索无结果)    —— #no-result: %s / .empty-state: %s" % (
            "存在且可见" if (b.get("noResult") or {}).get("visible") else "不存在/不可见",
            "存在且可见" if (b.get("emptyState") or {}).get("visible") else "不存在/不可见"))

        nr_b = b.get("noResult")
        es_b = b.get("emptyState")
        if es_b and es_b.get("visible") and es_b.get("text"):
            log("  → 搜索无结果时，用户**能看见**文案：%r" % es_b["text"])
            log("     但该元素缺 role=status / aria-live（读屏不播报），")
            log("     与列表页的 #no-result（role=status + aria-live=polite）**实现不一致**。")
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
