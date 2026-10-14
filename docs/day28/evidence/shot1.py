#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 28 · 截图 1：验收清单逐项打勾（报告页全页渲染）

报告页由本地 HTTP 服务提供：http://127.0.0.1:8898/acceptance-report.html
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:8898/acceptance-report.html"
OUT = os.path.join(HERE, "day28-截图1-验收清单逐项打勾.png")
PORT = 9381
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

log_lines = []


def log(m=""):
    log_lines.append(str(m))


def main():
    log("截图 1 开始")
    prof = os.path.join(HERE, "_s1_%d" % int(time.time() * 1000))
    env = dict(os.environ)
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        env.pop(k, None)

    proc = subprocess.Popen(
        [EDGE, "--new-window", "--user-data-dir=" + prof, "--no-first-run",
         "--no-default-browser-check", "--remote-debugging-port=%d" % PORT,
         "--remote-allow-origins=*", URL],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    log("已启动 Edge pid=%s" % proc.pid)

    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ws_url = None
    for i in range(50):
        time.sleep(1)
        try:
            ts = json.loads(op.open("http://127.0.0.1:%d/json" % PORT, timeout=4).read().decode())
        except Exception as e:
            log("  poll %d: %r" % (i, e))
            continue
        for t in ts:
            if t.get("type") == "page" and t.get("url", "").startswith("http"):
                ws_url = t["webSocketDebuggerUrl"]
                break
        if ws_url:
            log("  第 %d 秒拿到目标页" % (i + 1))
            break
    if not ws_url:
        log("!! 没拿到目标页")
        return

    ws = websocket.create_connection(ws_url, timeout=30, http_proxy_host=None)
    mid = [0]

    def send(m, p=None):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": m, "params": p or {}}))
        dl = time.time() + 30
        while time.time() < dl:
            try:
                ws.settimeout(1.5)
                msg = json.loads(ws.recv())
            except Exception:
                continue
            if msg.get("id") == mid[0]:
                return msg
        return None

    def ev(js):
        r = send("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
        return r["result"].get("result", {}).get("value") if r and "result" in r else None

    send("Runtime.enable")
    send("Page.enable")
    time.sleep(3)

    hh = ev("document.body.scrollHeight")
    ww = ev("document.body.scrollWidth")
    log("  报告页尺寸：%s x %s" % (ww, hh))

    send("Emulation.setDeviceMetricsOverride",
         {"width": 1180, "height": int(hh or 1600), "deviceScaleFactor": 2, "mobile": False})
    time.sleep(2)
    r = send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
    if r and "result" in r:
        with open(OUT, "wb") as f:
            f.write(base64.b64decode(r["result"]["data"]))
        log("  已写出 %s（%d 字节）" % (os.path.basename(OUT), os.path.getsize(OUT)))
    else:
        log("!! 截图失败")

    ws.close()
    time.sleep(0.5)
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("截图 1 结束")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("EXC: %r" % (e,))
    finally:
        with open(os.path.join(HERE, "_s1_log.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
