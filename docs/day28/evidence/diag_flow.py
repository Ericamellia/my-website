#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 · 诊断二：核心流程每一步的「真实 URL + DOM 状态」

上一次跑出「第1遍收藏页 2 条 / 第2遍 0 条」这种诡异的数，怀疑：
  ① 搜索三态测的时候页面并不在列表页（hash 不对）
  ② 每次导航后 render 没完成就读了 DOM（时序问题）
  ③ 收藏页的条目数受 favStar 渲染影响

这个脚本不打结论，只把每一步的 URL / hash / 关键节点数 全打出来，让数据说话。
"""
import json
import os
import subprocess
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "diag_flow_log.txt")
PORT = 9344

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


def snap(cdp, label):
    """抓一个完整快照：URL/hash/各关键节点数/localStorage。"""
    s = cdp.ev("""
    (function(){
      var fs=null; try{ fs=JSON.parse(localStorage.getItem('touhou_favs')||'[]'); }catch(e){}
      return {
        hash: location.hash,
        title: (document.querySelector('#app h2, #app h1')||{}).textContent || '',
        workItem: document.querySelectorAll('.work-item').length,
        videoCard: document.querySelectorAll('.video-card').length,
        favPanel: document.querySelectorAll('.fav-panel').length,
        favCardStar: document.querySelectorAll('.fav-card-star').length,
        searchBox: !!document.getElementById('globalSearch'),
        noResult: (function(){var n=document.getElementById('no-result');return n?('hidden='+n.hidden):'none';})(),
        lsFavs: (fs||[]).length,
      };
    })()
    """)
    log("  [%-22s] %s" % (label, json.dumps(s, ensure_ascii=False)))


def main():
    log("=" * 80)
    log("诊断二：核心流程每一步的真实状态")
    log("=" * 80)

    exe = None
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p):
            exe = p
            break

    prof = os.path.join(HERE, ".edge_diag2")
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
        log("\n--- A. 初始（首页）---")
        snap(cdp, "首页")

        log("\n--- B. 搜索三态（应在列表页做）---")
        cdp.ev("location.hash='#/music'; 'ok'")
        time.sleep(1.5)
        snap(cdp, "切到 music")
        cdp.ev("try{localStorage.removeItem('touhou_favs');}catch(e){}; 'ok'")

        cdp.ev("(function(){var i=document.getElementById('globalSearch');i.value='灵梦';i.dispatchEvent(new Event('input',{bubbles:true}));})()")
        time.sleep(1.3)
        snap(cdp, "搜'灵梦'")
        cdp.ev("(function(){var i=document.getElementById('globalSearch');i.value='zzzzzz';i.dispatchEvent(new Event('input',{bubbles:true}));})()")
        time.sleep(1.3)
        snap(cdp, "搜'zzzzzz'")
        cdp.ev("(function(){var i=document.getElementById('globalSearch');i.value='';i.dispatchEvent(new Event('input',{bubbles:true}));})()")
        time.sleep(1.3)
        snap(cdp, "清空搜索")

        log("\n--- C. 收藏流程：从干净的列表页开始 ---")
        cdp.ev("try{localStorage.removeItem('touhou_favs');}catch(e){}; 'ok'")
        cdp.ev("location.hash='#/'; 'ok'")
        time.sleep(1.5)
        snap(cdp, "回首页")

        cdp.ev("location.hash='#/music/1'; 'ok'")
        time.sleep(1.5)
        snap(cdp, "详情页 music/1")

        log("  点收藏按钮……")
        cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');if(b)b.click();})()")
        time.sleep(1.5)
        snap(cdp, "点收藏后(仍详情页)")

        cdp.ev("location.hash='#/fav'; 'ok'")
        time.sleep(1.8)
        snap(cdp, "收藏页（第1次）")

        log("\n--- D. 完全重来一次（模拟第 2 遍）---")
        cdp.ev("try{localStorage.removeItem('touhou_favs');}catch(e){}; 'ok'")
        cdp.ev("location.hash='#/'; 'ok'")
        time.sleep(1.5)
        snap(cdp, "回首页(第2遍)")
        cdp.ev("location.hash='#/music/1'; 'ok'")
        time.sleep(1.5)
        snap(cdp, "详情页 music/1(第2遍)")
        cdp.ev("(function(){var b=document.querySelector('#app .detail-cta-fav');if(b)b.click();})()")
        time.sleep(1.5)
        snap(cdp, "点收藏后(第2遍)")
        cdp.ev("location.hash='#/fav'; 'ok'")
        time.sleep(1.8)
        snap(cdp, "收藏页（第2次）")

        log("\n--- E. 关键追问：localStorage 到底存了什么 ---")
        v = cdp.ev("localStorage.getItem('touhou_favs')")
        log("  touhou_favs = %s" % v)
        v2 = cdp.ev("(function(){var fs=JSON.parse(localStorage.getItem('touhou_favs')||'[]');return fs.map(function(f){return f.module+'-'+f.id;});})()")
        log("  解析后 = %s" % json.dumps(v2, ensure_ascii=False))
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
