# -*- coding: utf-8 -*-
"""验证：① 热搜封面 hover 弹小窗 ② 点击开大图 ③ 大图有下载按钮 ④ 搜索框使用时拉长。"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request, urllib.parse

CDP_PORT = 9337
BASE = os.environ.get('BASE', 'http://127.0.0.1:3000')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-pop-')
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
        fp = os.path.join(OUTDIR, 'pop-' + name + '.png')
        open(fp, 'wb').write(base64.b64decode(d))
        return os.path.basename(fp)

    def mouse(x, y, kind='move'):
        if kind == 'move':
            cdp('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y})
        else:
            cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})
            cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})

    # ================= 搜索框：使用时拉长 =================
    cdp('Page.navigate', {'url': BASE + '/#/hot'})
    time.sleep(5)
    print('=' * 78)
    print('【顶栏搜索框：使用状态拉长】')
    w0 = ev('Math.round(document.querySelector(".header-search-wrap").getBoundingClientRect().width)')
    print('  未使用（失焦）宽度 =', w0, 'px')
    # 点击搜索框（聚焦）
    sb = ev('(function(){var i=document.getElementById("globalSearch");var r=i.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    mouse(sb['x'], sb['y'], 'click')
    time.sleep(0.9)
    w1 = ev('Math.round(document.querySelector(".header-search-wrap").getBoundingClientRect().width)')
    focused = ev('document.activeElement && document.activeElement.id')
    print('  使用中（聚焦）宽度 =', w1, 'px | 聚焦元素 =', focused)
    OK.append(('搜索框', '聚焦后变宽', isinstance(w1, int) and isinstance(w0, int) and w1 > w0, '%s→%s' % (w0, w1)))
    OK.append(('搜索框', '确实获得焦点', focused == 'globalSearch', focused))
    # 顶栏仍是一行
    tops = ev('Array.from(document.querySelectorAll("header nav .nav-item")).map(function(a){return Math.round(a.getBoundingClientRect().top)})')
    OK.append(('搜索框', '拉长后顶栏仍一行', len(set(tops or [])) == 1, tops))
    ovf = ev('document.documentElement.scrollWidth <= window.innerWidth + 1')
    OK.append(('搜索框', '拉长后无横向溢出', bool(ovf), ovf))
    print('  截图 →', shot('搜索框拉长', {'x': 0, 'y': 0, 'width': 1500, 'height': 110, 'scale': 2}))
    # 失焦收回
    ev('document.getElementById("globalSearch").blur()')
    time.sleep(0.6)
    w2 = ev('Math.round(document.querySelector(".header-search-wrap").getBoundingClientRect().width)')
    print('  失焦后宽度 =', w2, 'px')
    OK.append(('搜索框', '失焦后收回', isinstance(w2, int) and w2 == w0, '%s→%s' % (w1, w2)))

    # ================= 热搜封面：hover 弹小窗 =================
    print('-' * 78)
    print('【热搜封面 hover 弹小窗】')
    cov = ev('(function(){var c=document.querySelector(".hot2-box[data-board=fresh] .hot2-cover");var r=c.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),hasPop:!!c.querySelector(".hover-pop")}})()')
    print('  第1条封面 =', cov)
    OK.append(('hover小窗', '封面内含 hover-pop 结构', bool(cov) and cov.get('hasPop'), cov))
    if cov:
        # 先移开再移入，确保触发 hover
        mouse(10, 400)
        time.sleep(0.3)
        mouse(cov['x'], cov['y'])
        time.sleep(0.8)
        disp = ev('(function(){var p=document.querySelector(".hot2-box[data-board=fresh] .hot2-cover .hover-pop");return p?getComputedStyle(p).display:null})()')
        print('  hover 后小窗 display =', disp)
        OK.append(('hover小窗', 'hover 时弹出（display:block）', disp == 'block', disp))
        print('  截图 →', shot('hover小窗', {'x': 100, 'y': 90, 'width': 620, 'height': 420, 'scale': 1}))

    # ================= 点击封面 → 开大图 =================
    print('-' * 78)
    print('【点击封面 → 大图预览 + 下载按钮】')
    hidden0 = ev('document.getElementById("lightbox").hidden')
    print('  点击前 lightbox hidden =', hidden0)
    mouse(cov['x'], cov['y'], 'click')
    time.sleep(1.2)
    hidden1 = ev('document.getElementById("lightbox").hidden')
    lb_src = ev('(document.getElementById("lightbox-img")||{}).src')
    dl_exist = ev('!!document.getElementById("lightbox-dl")')
    dl_text = ev('(document.getElementById("lightbox-dl")||{}).textContent')
    print('  点击后 lightbox hidden =', hidden1, '| 图片 src 长度 =', len(str(lb_src or '')))
    print('  下载按钮存在 =', dl_exist, '| 文字 =', (dl_text or '').strip())
    OK.append(('大图', '点击封面打开大图', hidden1 is False, hidden1))
    OK.append(('大图', '大图有图片地址', bool(lb_src) and str(lb_src).startswith('http'), str(lb_src)[:60]))
    OK.append(('大图', '大图有下载按钮', bool(dl_exist), dl_exist))
    OK.append(('大图', '按钮文案=下载原图', '下载原图' in str(dl_text), dl_text))
    # 页面没有被跳走（点击封面不应跳 B 站）
    cur = ev('location.href')
    OK.append(('大图', '点击封面未跳转B站', 'bilibili.com' not in str(cur), str(cur)[:60]))
    print('  截图 →', shot('大图预览', {'x': 0, 'y': 0, 'width': 1500, 'height': 1000, 'scale': 1}))

    # 下载按钮：点击触发下载（用 DOM 事件验证 click 已绑定且不关大图）
    print('  —— 点下载按钮 ——')
    dlb = ev('(function(){var b=document.getElementById("lightbox-dl");var r=b.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    if dlb:
        mouse(dlb['x'], dlb['y'], 'click')
        time.sleep(1.5)
        still_open = ev('document.getElementById("lightbox").hidden === false')
        print('  点下载后大图仍打开 =', still_open, '（不应被误关）')
        OK.append(('大图', '点下载不误关大图', bool(still_open), still_open))
    # Esc 关闭
    cdp('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
    cdp('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
    time.sleep(0.6)
    closed = ev('document.getElementById("lightbox").hidden === true')
    print('  Esc 关闭大图 =', closed)
    OK.append(('大图', 'Esc 可关闭', bool(closed), closed))

    # ================= 详细页卡片同样支持 =================
    print('-' * 78)
    print('【详细页卡片：hover 小窗 + 点封面开大图】')
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/hot/fresh'})
    time.sleep(4.5)
    has_pop = ev('!!document.querySelector(".video-grid .hot2-open .hover-pop")')
    print('  详细页封面含 hover-pop =', has_pop)
    OK.append(('详细页', '卡片封面含 hover-pop', bool(has_pop), has_pop))
    vc = ev('(function(){var c=document.querySelector(".video-grid .hot2-open");if(!c)return null;var r=c.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
    if vc:
        mouse(vc['x'], vc['y'], 'click')
        time.sleep(1.2)
        h = ev('document.getElementById("lightbox").hidden')
        print('  点详细页封面 → 大图打开 =', h is False)
        OK.append(('详细页', '点封面开大图', h is False, h))
        print('  截图 →', shot('详细页大图', {'x': 0, 'y': 0, 'width': 1500, 'height': 900, 'scale': 1}))

    # ================= 回归 =================
    print('-' * 78)
    print('【回归：其他页面 hover 行为未被破坏】')
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/video'}); time.sleep(3.5)
    vpop = ev('document.querySelectorAll(".video-grid .video-card .hover-pop").length')
    vcard = ev('document.querySelectorAll(".video-grid .video-card").length')
    print('  同人视频 卡片=%s | 含hover-pop=%s' % (vcard, vpop))
    OK.append(('回归', '同人视频卡片正常', isinstance(vcard, int) and vcard > 0, vcard))
    OK.append(('回归', '视频卡片仍有hover小窗', isinstance(vpop, int) and vpop > 0, vpop))

    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/music'}); time.sleep(3.5)
    m = ev('document.querySelectorAll(".work-item").length')
    print('  同人音乐 卡片 =', m)
    OK.append(('回归', '同人音乐正常', isinstance(m, int) and m > 0, m))

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
