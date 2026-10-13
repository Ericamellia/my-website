# Day 27 截图：把本地 HTML 报告渲染成 PNG（用于交付截图）
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9345

url = sys.argv[1]          # file:///... 或 https://...
out = sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 1200
H = int(sys.argv[4]) if len(sys.argv) > 4 else 1600

profile = os.path.join(os.path.dirname(os.path.abspath(out)), "_rep_%d" % int(time.time() * 1000))
env = dict(os.environ)
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
    env.pop(k, None)

subprocess.Popen(
    [EDGE, "--new-window", "--user-data-dir=" + profile, "--no-first-run",
     "--no-default-browser-check", "--remote-debugging-port=%d" % PORT,
     "--remote-allow-origins=*", "--window-size=%d,%d" % (W, H), url],
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
        if t.get("type") == "page" and (t.get("url", "").startswith("file:") or "workbuddy" in t.get("url", "")):
            page = t
            break
    if page:
        break

if not page:
    print("page not found")
    sys.exit(1)
print("PAGE:", page["url"])

import websocket  # noqa: E402

ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30, http_proxy_host=None)
mid = [0]


def send(method, params=None):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    return mid[0]


def wait_id(target_id, timeout=25):
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
# 视口设为内容宽度，高度给足，captureBeyondViewport 截全页
send("Emulation.setDeviceMetricsOverride",
     {"width": W, "height": H, "deviceScaleFactor": 2, "mobile": False})
send("Page.reload", {"ignoreCache": True})
time.sleep(4)

r = wait_id(send("Page.captureScreenshot", {
    "format": "png", "captureBeyondViewport": True}), timeout=40)
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
shutil.rmtree(profile, ignore_errors=True)
