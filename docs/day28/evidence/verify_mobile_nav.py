# Day 28b 验证：顶栏回调 + 搜索框改小 + B站移动端风格 + 导航高亮
import base64, json, os, shutil, subprocess, sys, time, urllib.request

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9361
URL = "http://127.0.0.1:3000/"
outdir = os.path.dirname(os.path.abspath(__file__))
log = open(os.path.join(outdir, "verify_mobile_nav_log.txt"), "w", encoding="utf-8")

def say(*a):
    line = " ".join(str(x) for x in a)
    print(line); log.write(line + "\n"); log.flush()

profile = os.path.join(outdir, "_vn2_%d" % int(time.time() * 1000))
env = dict(os.environ)
for k in ("http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","all_proxy","ALL_PROXY"):
    env.pop(k, None)

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
if not page: say("page not found"); sys.exit(1)
say("PAGE:", page["url"])

import websocket
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30, http_proxy_host=None)
mid=[0]
def send(m,p=None):
    mid[0]+=1; ws.send(json.dumps({"id":mid[0],"method":m,"params":p or {}})); return mid[0]
def wait_id(i,t=20):
    dl=time.time()+t
    while time.time()<dl:
        try: ws.settimeout(1.5); msg=json.loads(ws.recv())
        except Exception: continue
        if msg.get("id")==i: return msg
    return None
def ev(js,t=20):
    r=wait_id(send("Runtime.evaluate",{"expression":js,"returnByValue":True,"awaitPromise":True}),t)
    return r["result"].get("result",{}).get("value") if r and "result" in r else None
def shot(name,beyond=True):
    r=wait_id(send("Page.captureScreenshot",{"format":"png","captureBeyondViewport":beyond}),30)
    if not r or "result" not in r: return
    data=base64.b64decode(r["result"]["data"])
    open(os.path.join(outdir,name),"wb").write(data)
    say("SAVED",name,len(data),"bytes")

send("Runtime.enable"); send("Page.enable")
send("Emulation.setDeviceMetricsOverride",{"width":390,"height":844,"deviceScaleFactor":3,"mobile":True})
send("Page.reload",{"ignoreCache":True}); time.sleep(7)

say("")
say("=== A. 顶栏高度 + 搜索框尺寸 ===")
say("[A]", ev("""(function(){
  var h=document.querySelector('header');
  var cs=document.getElementById('contentSearchBar');
  var gs=document.getElementById('globalSearch');
  var r=gs?gs.getBoundingClientRect():null;
  var s=gs?getComputedStyle(gs):null;
  return JSON.stringify({
    headerH: h?Math.round(h.getBoundingClientRect().height):-1,
    searchW: r?Math.round(r.width):-1,
    searchH: r?Math.round(r.height):-1,
    searchRadius: s?s.borderRadius:null,
    searchFont: s?s.fontSize:null,
    searchBg: s?s.backgroundColor:null,
    searchInContentBar: !!(cs&&gs&&cs.contains(gs))
  });
})()"""))

say("")
say("=== B. 导航高亮（进入音乐板块）===")
ev("location.hash='#/music'"); time.sleep(4)
say("[B]", ev("""(function(){
  var a=document.querySelector('header nav .nav-item.is-active');
  return JSON.stringify({
    activeHref: a?a.getAttribute('href'):null,
    activeColor: a?getComputedStyle(a).color:null,
    totalActive: document.querySelectorAll('header nav .nav-item.is-active').length,
    hasUnderline: a? getComputedStyle(a,'::after').width : null
  });
})()"""))
shot("day28b-1-音乐-顶栏回调.png")

say("")
say("=== C. 切板块后高亮跟随 ===")
ev("location.hash='#/video'"); time.sleep(4)
say("[C]", ev("JSON.stringify({hash:location.hash, active:(document.querySelector('header nav .nav-item.is-active')||{}).getAttribute?document.querySelector('header nav .nav-item.is-active').getAttribute('href'):null})"))
shot("day28b-2-视频-高亮跟随.png")

say("")
say("=== D. 滑动切板块仍正常 ===")
ev("location.hash='#/music'"); time.sleep(4)
ev("""(function(){
  function fire(type,x,y){
    var t=new Touch({identifier:1,target:document.body,clientX:x,clientY:y});
    document.dispatchEvent(new TouchEvent(type,{touches:type==='touchend'?[]:[t],changedTouches:[t],bubbles:true,cancelable:true}));
  }
  fire('touchstart',300,400); fire('touchend',120,405);
})()""")
time.sleep(4)
say("[D] 左滑后:", ev("JSON.stringify({hash:location.hash, h2:(document.querySelector('h2')||{}).textContent, active:(document.querySelector('header nav .nav-item.is-active')||{}).getAttribute?document.querySelector('header nav .nav-item.is-active').getAttribute('href'):null})"))

say("")
say("=== E. 桌面宽度回归 ===")
send("Emulation.setDeviceMetricsOverride",{"width":1280,"height":800,"deviceScaleFactor":1,"mobile":False})
time.sleep(2); send("Page.reload",{"ignoreCache":True}); time.sleep(6)
say("[E]", ev("""(function(){
  var gs=document.getElementById('globalSearch');
  var cs=document.getElementById('contentSearchBar');
  var h=document.querySelector('header');
  return JSON.stringify({
    searchInHeader: !!(gs&&gs.closest('header')),
    contentBarHidden: cs?cs.hidden:null,
    headerH: h?Math.round(h.getBoundingClientRect().height):-1,
    navActiveCount: document.querySelectorAll('header nav .nav-item.is-active').length
  });
})()"""))
shot("day28b-4-桌面回归.png", beyond=False)

ws.close(); time.sleep(0.5)
os.system('taskkill /F /IM msedge.exe >nul 2>&1'); time.sleep(1)
shutil.rmtree(profile, ignore_errors=True); log.close()
