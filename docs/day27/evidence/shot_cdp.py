# Day 27 截图：用 CDP 打开真实浏览器窗口，滚动到作品列表，截取「社团名已显示」
#
# 为什么要滚动：作品卡片在首屏下方，不滚动截不到社团名 ——
# 而「社团名显示出来」正是本次修复的证据。
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9341

url = sys.argv[1]
out = sys.argv[2]
scroll_js = sys.argv[3] if len(sys.argv) > 3 else ""
wait = float(sys.argv[4]) if len(sys.argv) > 4 else 8.0

profile = os.path.join(os.path.dirname(os.path.abspath(out)),
                       "_cdpprofile_%d" % int(time.time() * 1000))
env = dict(os.environ)
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
    env.pop(k, None)

subprocess.Popen(
    [EDGE, "--start-maximized", "--new-window",
     "--user-data-dir=" + profile, "--no-first-run",
     "--no-default-browser-check",
     "--remote-debugging-port=%d" % PORT,
     "--remote-allow-origins=*", url],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
page = None
for _ in range(40):
    time.sleep(1)
    try:
        targets = json.loads(op.open("http://127.0.0.1:%d/json" % PORT, timeout=5).read().decode())
    except Exception:
        continue
    for t in targets:
        if t.get("type") == "page" and "workbuddy.host" in t.get("url", ""):
            page = t
            break
    if page:
        break

if not page:
    print("page not found")
    sys.exit(1)
print("PAGE:", page["url"])

import websocket  # noqa: E402

ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30,
                                 http_proxy_host=None)
mid = [0]


def send(method, params=None):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    return mid[0]


def wait_id(target_id, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ws.settimeout(1.5)
            msg = json.loads(ws.recv())
        except Exception:
            continue
        if msg.get("id") == target_id:
            return msg
    return None


send("Runtime.enable")
send("Page.enable")
send("Page.reload", {"ignoreCache": True})
time.sleep(wait)   # 等页面渲染完（含 JS 拉数据）

# 执行滚动 JS
if scroll_js:
    r = wait_id(send("Runtime.evaluate", {
        "expression": scroll_js, "returnByValue": True, "awaitPromise": True
    }), timeout=20)
    if r and r.get("result", {}).get("result", {}).get("value") is not None:
        print("JS 返回:", r["result"]["result"]["value"])
    time.sleep(2.5)

# 截全页
r = wait_id(send("Page.captureScreenshot", {
    "format": "png", "captureBeyondViewport": True
}), timeout=30)
if not r or "result" not in r:
    print("截图失败:", r)
    sys.exit(1)

data = base64.b64decode(r["result"]["data"])
with open(out, "wb") as f:
    f.write(data)
print("SAVED %s %d bytes" % (out, len(data)))

ws.close()
time.sleep(0.5)
os.system('taskkill /F /IM msedge.exe >nul 2>&1')
time.sleep(1)
import shutil
shutil.rmtree(profile, ignore_errors=True)
