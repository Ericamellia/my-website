# Day 27 余力加练：用手机宽度（390x844）走完一次完整核心流程并截图
#
# 核心流程：首页 -> 切板块（同人音乐）-> 点收藏 -> 看收藏列表
# 与桌面版截图脚本的区别：多一步 Emulation.setDeviceMetricsOverride 强制手机视口。
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9343
DEV_W, DEV_H, DPR, MOBILE = 390, 844, 3, True

url = "https://touhou-mock.app.workbuddy.host/"
outdir = os.path.dirname(os.path.abspath(__file__))
log = open(os.path.join(outdir, "mobile_trial_log.txt"), "w", encoding="utf-8")


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    log.write(line + "\n")
    log.flush()


profile = os.path.join(outdir, "_mobprofile_%d" % int(time.time() * 1000))
env = dict(os.environ)
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
    env.pop(k, None)

subprocess.Popen(
    [EDGE, "--new-window", "--user-data-dir=" + profile, "--no-first-run",
     "--no-default-browser-check", "--remote-debugging-port=%d" % PORT,
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
    say("page not found")
    sys.exit(1)
say("PAGE:", page["url"])

import websocket  # noqa: E402

ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30, http_proxy_host=None)
mid = [0]


def send(method, params=None):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    return mid[0]


def wait_id(target_id, timeout=20):
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


def ev(js, timeout=20):
    r = wait_id(send("Runtime.evaluate", {
        "expression": js, "returnByValue": True, "awaitPromise": True}), timeout=timeout)
    if r and "result" in r:
        return r["result"].get("result", {}).get("value")
    return None


def shot(name):
    r = wait_id(send("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": True}), timeout=30)
    if not r or "result" not in r:
        say("截图失败:", name)
        return None
    data = base64.b64decode(r["result"]["data"])
    p = os.path.join(outdir, name)
    with open(p, "wb") as f:
        f.write(data)
    say("SAVED %s %d bytes" % (name, len(data)))
    return p


send("Runtime.enable")
send("Page.enable")
send("Emulation.setDeviceMetricsOverride", {
    "width": DEV_W, "height": DEV_H, "deviceScaleFactor": DPR, "mobile": MOBILE})
say("设备模拟已设置: %dx%d dpr=%d mobile=%s" % (DEV_W, DEV_H, DPR, MOBILE))

send("Page.reload", {"ignoreCache": True})
time.sleep(7)

steps = []

# --- 步骤 1：首页 ---
vp = ev("JSON.stringify({w:innerWidth,h:innerHeight,title:document.title,"
        "nav:document.querySelectorAll('.nav-item').length,"
        "loading:!!document.querySelector('.loading-state')})")
say("[1] 首页视口:", vp)
steps.append(("首页", vp))
shot("mobile-1-首页.png")

# --- 步骤 2：切到「同人音乐」板块 ---
r = ev("""(function(){
  var items=document.querySelectorAll('.nav-item');
  for(var i=0;i<items.length;i++){
    var t=(items[i].textContent||'').trim();
    if(t.indexOf('音乐')>=0){ items[i].click(); return 'clicked:'+t; }
  }
  return 'nav-not-found:'+items.length;
})()""")
say("[2] 点击同人音乐导航:", r)
time.sleep(6)
r2 = ev("""JSON.stringify({
  hash:location.hash,
  cards:document.querySelectorAll('.work-card,.card,[class*=card]').length,
  firstCard:(document.querySelector('.work-card,.card,[class*=card]')||{}).innerText||'',
  bodyHead:document.body.innerText.slice(0,160)
})""")
say("[2] 板块内容:", r2)
steps.append(("同人音乐板块", r2))
shot("mobile-2-同人音乐.png")

# --- 步骤 3a：点第一张卡片，进详情页（收藏按钮只在详情页）---
r = ev("""(function(){
  var a=document.querySelector('.work-item .card-thumb')||document.querySelector('a[href^="#/music/"]');
  if(!a) return 'no-card-link';
  var href=a.getAttribute('href');
  location.hash=href.replace(/^#/,'');
  return 'goto:'+href;
})()""")
say("[3a] 进入详情页:", r)
time.sleep(6)
r = ev("""JSON.stringify({
  hash:location.hash,
  favBtns:document.querySelectorAll('.detail-cta-fav').length,
  head:document.body.innerText.slice(0,200)
})""")
say("[3a] 详情页内容:", r)
steps.append(("作品详情页", r))
shot("mobile-3-详情页.png")

# --- 步骤 3b：点详情页的收藏按钮 ---
r = ev("""(function(){
  var b=document.querySelector('.detail-cta-fav');
  if(!b) return 'no-detail-fav-btn';
  b.click();
  return 'clicked-detail-fav; now='+(b.className||'');
})()""")
say("[3b] 点击详情页收藏:", r)
time.sleep(3)
r = ev("""(function(){
  try{ var f=JSON.parse(localStorage.getItem('touhou_favs')||'[]');
    return 'favs='+f.length+' '+JSON.stringify(f.slice(-2));
  }catch(e){ return 'read-err:'+e.message; }
})()""")
say("[3b] localStorage 收藏数:", r)
steps.append(("点击收藏后", r))
shot("mobile-4-已收藏.png")

# --- 步骤 4：进收藏列表 ---
r = ev("""(function(){
  var items=document.querySelectorAll('.nav-item,a,button');
  for(var i=0;i<items.length;i++){
    var t=(items[i].textContent||'').trim();
    if(t.indexOf('收藏')>=0){ items[i].click(); return 'clicked:'+t; }
  }
  return 'fav-nav-not-found';
})()""")
say("[4] 点击收藏导航:", r)
time.sleep(5)
r2 = ev("""JSON.stringify({
  hash:location.hash,
  cards:document.querySelectorAll('.fav-work-list .work-item').length,
  stars:document.querySelectorAll('.fav-card-star').length,
  bodyHead:document.body.innerText.slice(0,240)
})""")
say("[4] 收藏列表内容:", r2)
steps.append(("收藏列表", r2))
shot("mobile-5-收藏列表.png")

# --- 汇总 ---
say("")
say("=== 手机宽度核心流程小结（390x844）===")
for name, val in steps:
    say("-", name, "=>", val)

ws.close()
time.sleep(0.5)
os.system('taskkill /F /IM msedge.exe >nul 2>&1')
time.sleep(1)
shutil.rmtree(profile, ignore_errors=True)
log.close()
