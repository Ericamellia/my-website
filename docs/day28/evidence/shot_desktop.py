# 桌面端顶栏复检：不覆盖设备参数，用真实窗口截图
import base64, json, os, shutil, subprocess, sys, time, urllib.request
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9355
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "day28-4-桌面顶栏搜索框.png")
profile = os.path.join(os.path.dirname(out), "_dsk_%d" % int(time.time()*1000))
env = dict(os.environ)
for k in ("http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","all_proxy","ALL_PROXY"):
    env.pop(k, None)
subprocess.Popen([EDGE,"--new-window","--user-data-dir="+profile,"--no-first-run",
  "--no-default-browser-check","--remote-debugging-port=%d"%PORT,"--remote-allow-origins=*",
  "--window-size=1280,820", "http://127.0.0.1:3000/"],
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
send("Runtime.enable"); send("Page.enable")
send("Page.reload",{"ignoreCache":True}); time.sleep(7)
# 滚动到音乐列表
r=wait_id(send("Runtime.evaluate",{"expression":"location.hash='#/music';'ok'","returnByValue":True}),15)
time.sleep(5)
resp=wait_id(send("Page.captureScreenshot",{"format":"png","fromSurface":True}),30)
if resp and "result" in resp:
    data=base64.b64decode(resp["result"]["data"])
    open(out,"wb").write(data)
    open(os.path.join(os.path.dirname(out),"desk_shot_log.txt"),"w").write("SAVED %d bytes\n"%len(data))
else:
    open(os.path.join(os.path.dirname(out),"desk_shot_log.txt"),"w").write("FAIL %s\n"%resp)
ws.close(); time.sleep(0.5)
os.system('taskkill /F /IM msedge.exe >nul 2>&1'); time.sleep(1)
shutil.rmtree(profile, ignore_errors=True)
