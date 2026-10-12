# -*- coding: utf-8 -*-
"""验证热搜详细页「返回/首页」按钮已整合进顶栏：
   ① 详细页内不再有重复的 .breadcrumb / 页面级返回首页按钮
   ② 顶栏 .brand 里的 backBtn + home-link 存在且可见
   ③ 顶栏「返回」可用（从 #/hot 进详细页后点返回 → 回到 #/hot）
   ④ 顶栏「首页」可用（点首页 → 回到 #/）
   ⑤ 回归：详细页 6 行分页仍正常
"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9345
BASE = os.environ.get('BASE', 'http://127.0.0.1:3001')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-hdr-')
proc = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1500,1200', 'about:blank'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws = None
OK = []
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
    w = create_connection(ws, timeout=40)
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
        rr = r.get('result', {})
        if rr.get('exceptionDetails'):
            return None
        return rr.get('result', {}).get('value')

    def shot(name, clip=None):
        p = {'format': 'png'}
        if clip:
            p['clip'] = clip
        r = cdp('Page.captureScreenshot', p)
        d = r.get('result', {}).get('data')
        if not d:
            return None
        fp = os.path.join(OUTDIR, 'hdr-' + name + '.png')
        open(fp, 'wb').write(base64.b64decode(d))
        return os.path.basename(fp)

    def click_at(sel_js):
        b = ev('(function(){var e=%s;if(!e)return null;e.scrollIntoView({block:"center"});'
               'var r=e.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()' % sel_js)
        if not b:
            return False
        cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': b['x'], 'y': b['y'], 'button': 'left', 'clickCount': 1})
        cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': b['x'], 'y': b['y'], 'button': 'left', 'clickCount': 1})
        return True

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})

    # ============ 先到首页，再进热搜主界面，再点进详细页（保证历史栈正常） ============
    cdp('Page.navigate', {'url': BASE + '/'}); time.sleep(4)
    ev('location.hash = "#/hot"'); time.sleep(2.5)
    ev('location.hash = "#/hot/fresh"'); time.sleep(3.5)
    for _ in range(20):
        n = ev('document.querySelectorAll("#hotDetailGrid .video-card").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)

    print('=' * 78)
    print('【详细页顶部：不再有重复的返回/首页】')
    bc = ev('document.querySelectorAll("#app .breadcrumb, #app .detail-nav, #app .home-back").length')
    hf = ev('document.querySelectorAll("#app .home-fab").length')
    print('  页内 breadcrumb/detail-nav/home-back 数量 =', bc)
    print('  页内 .home-fab 数量 =', hf)
    OK.append(('详细页', '页内无重复返回/首页按钮', bc == 0 and hf == 0, 'bc=%s hf=%s' % (bc, hf)))
    h2 = ev('(function(){var h=document.querySelector("#app h2");return h?h.textContent.trim():null})()')
    print('  页面首个标题 =', h2)
    OK.append(('详细页', '标题直接就是榜单名', h2 == '今日B站热搜', h2))
    print('  截图 →', shot('详细页顶部', {'x': 0, 'y': 0, 'width': 1500, 'height': 420, 'scale': 2}))

    # ============ 顶栏按钮存在且可见 ============
    print('-' * 78)
    print('【顶栏：返回 / 首页 按钮】')
    back = ev('(function(){var b=document.getElementById("backBtn");if(!b)return null;var r=b.getBoundingClientRect();return {vis:r.width>0&&r.height>0,x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    home = ev('(function(){var a=document.querySelector("header .brand a.home-link");if(!a)return null;var r=a.getBoundingClientRect();return {vis:r.width>0&&r.height>0,x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    print('  返回按钮 =', back)
    print('  首页按钮 =', home)
    OK.append(('顶栏', '返回按钮可见', bool(back) and back.get('vis'), back))
    OK.append(('顶栏', '首页按钮可见', bool(home) and home.get('vis'), home))
    tops = ev('Array.from(document.querySelectorAll("header .brand > *")).map(function(e){return Math.round(e.getBoundingClientRect().top)})')
    print('  brand 子元素 top =', tops)

    # ============ 顶栏返回：详细页 → 回 #/hot ============
    print('-' * 78)
    print('【顶栏「返回」：详细页 → 热搜主界面】')
    click_at('document.getElementById("backBtn")')
    time.sleep(1.5)
    h1 = ev('location.hash')
    print('  点返回后 hash =', h1)
    OK.append(('顶栏返回', '回到 #/hot', h1 in ('#/hot', '#/hot/'), h1))

    # ============ 顶栏首页：→ #/ ============
    print('-' * 78)
    print('【顶栏「首页」】')
    ev('location.hash = "#/hot/fresh"'); time.sleep(2.5)
    click_at('document.querySelector("header .brand a.home-link")')
    time.sleep(1.5)
    h2_ = ev('location.hash')
    print('  点首页后 hash =', h2_)
    OK.append(('顶栏首页', '回到 #/', h2_ in ('#/', '', '#'), h2_))

    # ============ 回归：详细页 6 行分页 ============
    print('-' * 78)
    print('【回归：详细页仍是 6 行 + 展开更多】')
    ev('location.hash = "#/hot/hot"'); time.sleep(3.5)
    for _ in range(20):
        n = ev('document.querySelectorAll("#hotDetailGrid .video-card").length')
        if isinstance(n, int) and n > 0:
            break
        time.sleep(0.5)
    shown = ev('document.querySelectorAll("#hotDetailGrid .video-card:not(.lm-hidden)").length')
    cols = ev('(function(){var cs=Array.from(document.querySelectorAll("#hotDetailGrid .video-card:not(.lm-hidden)"));if(!cs.length)return 0;var t=cs[0].offsetTop;return cs.filter(function(c){return c.offsetTop===t}).length})()')
    rows = round(shown / cols) if (shown and cols) else 0
    btxt = ev('(function(){var b=document.querySelector(".load-more-btn");return b?b.textContent.trim():null})()')
    print('  首屏 = %s 条 / %s 列 = %s 行 | 按钮 = %s' % (shown, cols, rows, btxt))
    OK.append(('回归', '详细页首屏 6 行', rows == 6, '%s/%s=%s' % (shown, cols, rows)))

finally:
    print()
    print('=' * 78)
    bad = [x for x in OK if not x[2]]
    print('汇总：检查 %d 项，通过 %d，失败 %d' % (len(OK), len(OK) - len(bad), len(bad)))
    for n_, l, ok, v in bad:
        print('  ❌ %s / %s → %s' % (n_, l, v))
    try:
        proc.kill()
    except Exception:
        pass
