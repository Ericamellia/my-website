# -*- coding: utf-8 -*-
"""取证：顶栏 8 个入口的实际渲染颜色 + 火焰与收藏的色差。"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9334
BASE = 'http://127.0.0.1:3000'
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-color-')
proc = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1500,1000', 'about:blank'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws = None
try:
    for _ in range(40):
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
                tg = json.load(r)
            pg = [t for t in tg if t.get('type') == 'page']
            if pg:
                ws = pg[0]['webSocketDebuggerUrl']; break
        except Exception:
            pass
        time.sleep(0.5)
    if not ws:
        print('无法连接 CDP'); sys.exit(1)

    from websocket import create_connection
    w = create_connection(ws, timeout=30)
    mid = [0]

    def cdp(m, p=None):
        mid[0] += 1
        w.send(json.dumps({'id': mid[0], 'method': m, 'params': p or {}}))
        while True:
            r = json.loads(w.recv())
            if r.get('id') == mid[0]:
                return r

    def ev(expr):
        r = cdp('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        return r.get('result', {}).get('result', {}).get('value')

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})
    cdp('Page.navigate', {'url': BASE + '/'})
    time.sleep(4)

    print('=' * 76)
    print('顶栏 8 个入口的实际渲染颜色（取 <svg> 的 computed color）')
    print('=' * 76)
    data = ev('''(function(){
      return Array.from(document.querySelectorAll("header nav .nav-item")).map(function(a,i){
        var svg = a.querySelector("svg");
        var cs = svg ? getComputedStyle(svg) : null;
        return {
          i: i+1,
          cls: a.className,
          aria: a.getAttribute("aria-label"),
          color: cs ? cs.color : null
        };
      });
    })()''')
    for d in (data or []):
        print('  %d. %-12s %-22s color=%s' % (d['i'], d['aria'], d['cls'], d['color']))

    print()
    print('=' * 76)
    print('顶栏底色 vs 火焰色 / 收藏色 对比')
    print('=' * 76)
    bg = ev('getComputedStyle(document.querySelector("header")).backgroundColor')
    hot = ev('getComputedStyle(document.querySelector(".nav-hot svg")).color')
    fav = ev('getComputedStyle(document.querySelector(".nav-fav svg")).color')
    print('  header 底色   =', bg)
    print('  B站必看(火焰) =', hot)
    print('  我的收藏(星)  =', fav)
    print()
    if hot and hot.startswith('rgb') and fav and fav.startswith('rgb'):
        def rgb(s):
            return [int(x) for x in s[s.index('(')+1:s.index(')')].split(',')[:3]]
        h, f = rgb(hot), rgb(fav)
        d = sum(abs(a-b) for a, b in zip(h, f))
        print('  火焰 vs 收藏 RGB =', h, 'vs', f, '→ 通道差合计 =', d)
        print('  结论：', '可明显区分（差值>150）' if d > 150 else '色差偏小，需再拉开')

finally:
    try:
        proc.kill()
    except Exception:
        pass
