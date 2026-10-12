# -*- coding: utf-8 -*-
"""验证【线上公网站点】：作品站 + 验证页 + 真库数据。"""
import json, urllib.request, os, subprocess, sys, io, time, socket, base64, tempfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
CDP_PORT = 9236
BASE = 'https://touhou-mock.app.workbuddy.host'

os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

profile = tempfile.mkdtemp(prefix='edge-live-')
edge = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1440,900', 'about:blank'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

target = None
for _ in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
            pages = [t for t in json.loads(r.read().decode()) if t.get('type') == 'page']
        if pages:
            target = pages[0]; break
    except Exception:
        pass
    time.sleep(0.5)

ws = target['webSocketDebuggerUrl'][5:]
hp, _, pth = ws.partition('/')
host, _, prt = hp.partition(':')
sk = socket.create_connection((host, int(prt)), timeout=25)
kk = base64.b64encode(os.urandom(16)).decode()
sk.sendall(('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
            'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (pth, hp, kk)).encode())
b = b''
while b'\r\n\r\n' not in b:
    b += sk.recv(4096)
cnt = [0]
errs = []


def snd(d):
    p = d.encode(); m = os.urandom(4); n = len(p)
    h = bytearray([0x81])
    if n < 126: h.append(0x80 | n)
    elif n < 65536: h.append(0x80 | 126); h += struct.pack('>H', n)
    else: h.append(0x80 | 127); h += struct.pack('>Q', n)
    h += m
    sk.sendall(bytes(h) + bytes(x ^ m[i % 4] for i, x in enumerate(p)))


def rcv():
    def rd(n):
        d = b''
        while len(d) < n:
            c = sk.recv(n - len(d))
            if not c: raise IOError('closed')
            d += c
        return d
    h = rd(2); ln = h[1] & 0x7F
    if ln == 126: ln = struct.unpack('>H', rd(2))[0]
    elif ln == 127: ln = struct.unpack('>Q', rd(8))[0]
    return rd(ln).decode('utf-8', 'ignore')


def cdp(method, params=None):
    cnt[0] += 1; mid = cnt[0]
    snd(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(rcv())
        if m.get('id') == mid:
            return m
        if m.get('method') == 'Runtime.exceptionThrown':
            d = (m.get('params') or {}).get('exceptionDetails') or {}
            errs.append(d.get('text'))
        if m.get('method') == 'Network.loadingFailed':
            p = m.get('params') or {}
            errs.append('loadFail %s %s' % (p.get('type'), p.get('errorText')))


cdp('Runtime.enable'); cdp('Page.enable'); cdp('Network.enable')
cdp('Network.setCacheDisabled', {'cacheDisabled': True})


def ev(e):
    r = cdp('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    return ((r.get('result') or {}).get('result') or {}).get('value')


def shot(n):
    r = cdp('Page.captureScreenshot', {'format': 'png'})
    d = ((r.get('result') or {}).get('data') or '')
    if d:
        p = os.path.join(OUTDIR, 'live-' + n + '.png')
        open(p, 'wb').write(base64.b64decode(d))
        return os.path.basename(p)


OK = []


def visit(name, route, checks, snap=False):
    cdp('Page.navigate', {'url': BASE + '/' + route})
    time.sleep(5)
    print('-' * 74)
    print('【%s】 %s/%s' % (name, BASE, route))
    src = ev('window.__dataSource || "(非作品站页面)"')
    print('  数据源 =', src)
    if snap:
        print('  截图 →', shot(name))
    for label, expr, expect in checks:
        v = ev(expr)
        ok = (v == expect) if expect is not None else bool(v)
        OK.append((name, label, ok, v))
        print('  [%s] %-22s → %s' % ('✓' if ok else '❌', label,
                                     json.dumps(v, ensure_ascii=False)[:100] if not isinstance(v, str) else v[:100]))


try:
    print()
    print('=' * 74)
    print('线上公网站点验证：' + BASE)
    print('=' * 74)

    visit('作品站首页', '', [
        ('数据源', 'window.__dataSource', 'api'),
        ('模块卡数', 'document.querySelectorAll(".module-card").length', 6),
        ('标题', 'document.title', None),
        ('图片加载', "(function(){var a=[].slice.call(document.images);return a.length+'张/'+a.filter(function(i){return i.complete&&i.naturalWidth>0}).length+'成功'})()", None),
    ], snap=True)

    for nm, rt, c in [('同人音乐', '#/music', 6), ('同人漫画', '#/doujin', 6), ('同人游戏', '#/game', 5),
                      ('同人视频', '#/video', 6), ('同人图', '#/art', 7)]:
        visit(nm, rt, [('卡片数', 'document.querySelectorAll(".work-item,.video-card").length', c)])

    visit('原作页', '#/original', [('原作卡片数', 'document.querySelectorAll(".og-card").length', 78)], snap=True)

    visit('音乐详情', '#/music/1', [
        ('作品名', '((document.querySelector("#app h2")||{}).textContent||"").trim()', 'ハルトマンの妖怪少女'),
        ('封面加载', 'document.querySelector("#app img.zoomable") ? document.querySelector("#app img.zoomable").complete : false', True),
        ('操作按钮', 'document.querySelectorAll(".detail-cta").length', 3),
    ], snap=True)

    visit('视频详情', '#/video/1', [
        ('B站链接', '(function(){var a=[].slice.call(document.querySelectorAll("a")).filter(function(x){return /bilibili\\.com\\/video/.test(x.href)});return a.length?a[0].href:""})()', None),
    ])

    visit('角色反查', '#/character/博丽灵梦', [
        ('字数', 'document.getElementById("app").textContent.trim().length', None),
    ], snap=True)

    visit('社团页', '#/circle/A-One', [('字数', 'document.getElementById("app").textContent.trim().length', None)])

    visit('搜索页', '#/search/灵梦', [('结果数', 'document.querySelectorAll(".work-item,.video-card").length', 7)])

    # 验证页
    cdp('Page.navigate', {'url': BASE + '/verify/'})
    time.sleep(4)
    print('-' * 74)
    print('【验证页】 %s/verify/' % BASE)
    t = ev('document.title')
    n = ev('document.body.textContent.trim().length')
    f = ev('/收藏/.test(document.body.textContent)')
    print('  标题 =', t)
    print('  文字长度 =', n, ' 含收藏模块 =', f)
    print('  截图 →', shot('验证页'))
    OK.append(('验证页', '标题', bool(t), t))
    OK.append(('验证页', '内容', n and n > 200, n))
    OK.append(('验证页', '收藏模块', f, f))

finally:
    print()
    print('=' * 74)
    bad = [x for x in OK if not x[2]]
    print('汇总：检查 %d 项，通过 %d，失败 %d' % (len(OK), len(OK) - len(bad), len(bad)))
    for n_, l, ok, v in bad:
        print('  ❌ %s / %s → %s' % (n_, l, v))
    if errs:
        print('  页面错误事件（前 5 条）:')
        for e in errs[:5]:
            print('    ', str(e)[:120])
    edge.kill()
    import shutil
    shutil.rmtree(profile, ignore_errors=True)
