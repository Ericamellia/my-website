# Day 28b：真实视口截图（不带 captureBeyondViewport），避免 sticky 顶栏错位
import base64, json, os, shutil, subprocess, sys, time, urllib.request
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9363
URL = "http://127.0.0.1:3000/"
outdir = os.path.dirname(os.path.abspath(__file__))

profile = os.path.join(outdir, "_vp_%d" % int(time.time()*1000))
env = dict(os.environ)
for k in ("http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","all_proxy","ALL_PROXY"): env.pop(k, None)
subprocess.Popen([EDGE,"--new-window","--user-data-dir="+profile,"--no-first-run",
  "--no-default-browser-check","--remote-debugging-port=%d"%PORT,"--remote-allow-origins=*",URL],
  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
page=None
for _ in range(40):
    time.sleep(1)
    try: ts=json.loads(op.open("http://127.0.0.1:%d/json"%PORT,timeout=5).read().decode())
    except Exception: continue
    for t in ts:
        if t.get("type")=="page" and "127.0.0.1:3000" in t.get("url",""): page=t; break
    if page: break
if not page: print("no page"); sys.exit(1)
import websocket
ws=websocket.create_connection(page["webSocketDebuggerUrl"],timeout=30,http_proxy_host=None)
mid=[0]
def send(m,p=None):
    mid[0]+=1; ws.send(json.dumps({"id":mid[0],"method":m,"params":p or {}})); return mid[0]
def wait_id(i,t=25):
    dl=time.time()+t
    while time.time()<dl:
        try: ws.settimeout(1.5); msg=json.loads(ws.recv())
        except Exception: continue
        if msg.get("id")==i: return msg
    return None
def ev(js,t=20):
    r=wait_id(send("Runtime.evaluate",{"expression":js,"returnByValue":True,"awaitPromise":True}),t)
    return r["result"].get("result",{}).get("value") if r and "result" in r else None
def shot(name):
    r=wait_id(send("Page.captureScreenshot",{"format":"png"}),30)
    if not r or "result" not in r: return
    open(os.path.join(outdir,name),"wb").write(base64.b64decode(r["result"]["data"]))

send("Runtime.enable"); send("Page.enable")
send("Emulation.setDeviceMetricsOverride",{"width":390,"height":844,"deviceScaleFactor":3,"mobile":True})
send("Page.reload",{"ignoreCache":True}); time.sleep(7)
ev("location.hash='#/music'"); time.sleep(5)
ev("window.scrollTo(0,0)"); time.sleep(1)
shot("day28b-0-手机首屏-真实视口.png")
# 滚动到卡片中间看卡片风格
ev("window.scrollTo(0,420)"); time.sleep(1.5)
shot("day28b-3-卡片风格.png")
ws.close(); time.sleep(0.5)
os.system('taskkill /F /IM msedge.exe >nul 2>&1'); time.sleep(1)
shutil.rmtree(profile, ignore_errors=True)
