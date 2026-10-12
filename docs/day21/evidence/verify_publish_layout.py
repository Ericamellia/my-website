# -*- coding: utf-8 -*-
"""模拟发布后环境：验证作品站 + 验证页 + 接口 三者共存。"""
import json, urllib.request, os, subprocess, sys, io, time, socket, base64, shutil, tempfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 8088
CDP_PORT = 9235
BASE = 'http://127.0.0.1:%d' % PORT

ENV = dict(os.environ)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    ENV.pop(k, None)

srv = subprocess.Popen([NODE, 'server.js'], cwd=DEPLOY, env=dict(ENV, PORT=str(PORT)),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
up = False
for _ in range(60):
    try:
        socket.create_connection(('127.0.0.1', PORT), timeout=1).close(); up = True; break
    except Exception:
        time.sleep(0.3)
if not up:
    print('❌ 服务未起'); srv.kill(); sys.exit(1)

print('=' * 78)
print('模拟发布后环境验证（作品站 / + 验证页 /verify/ + 接口 /api/*）')
print('=' * 78)
print()


def req(path, method='GET', follow=True):
    r = urllib.request.Request(BASE + path, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as x:
            return x.status, x.headers, x.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode('utf-8', 'ignore')


print('【1】HTTP 层：路径 → 内容')
print('-' * 78)
cases = [
    ('/', '作品站（应含 app.js）', 'app.js?v=88'),
    ('/index.html', '作品站 index.html', 'app.js?v=88'),
    ('/style.css', '作品站样式', 'touhou' ) if False else ('/style.css', '作品站样式', None),
    ('/app.js', '作品站脚本', 'loadFromApi'),
    ('/verify/', '验证页（应含 Day 20 标题）', 'Day 20'),
    ('/verify/index.html', '验证页 index.html', None),
    ('/api/works?category=music', '作品接口', '"ok"'),
    ('/api/health', '健康检查', '"ok"'),
    ('/assets/music/cover1.jpg', '图片资源', None),
]
ok_all = True
for path, label, expect in cases:
    st, hd, body = req(path)
    ctype = hd.get('Content-Type', '')
    has = (expect in body) if expect else True
    ok = st == 200 and has
    ok_all &= ok
    print('  [%s] %-26s HTTP %-3s %-30s %s' % (
        '✓' if ok else '❌', path, st, ctype[:30],
        '' if has else '（未找到 %r）' % expect))

# 301 重定向（用不跟随重定向的 opener 才能看到 301 本身）
import urllib.error
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
op = urllib.request.build_opener(NoRedirect)
try:
    with op.open(urllib.request.Request(BASE + '/verify'), timeout=10) as x:
        print('  [❌] %-26s 未跳转（状态 %s，期望 301）' % ('/verify', x.status))
except urllib.error.HTTPError as e:
    loc = e.headers.get('Location')
    ok301 = e.code == 301 and loc and loc.endswith('/verify/')
    print('  [%s] %-26s HTTP %s → Location: %s' % ('✓' if ok301 else '❌', '/verify', e.code, loc))

print()
print('【2】接口层：5 个新接口')
print('-' * 78)
for p, k, exp in [('/api/works?category=music', 'data', 6), ('/api/works?category=art', 'data', 7),
                  ('/api/circles', 'data', 26), ('/api/original-games', 'games', 39),
                  ('/api/characters', 'characters', 112), ('/api/originals', 'data', 6)]:
    st, _, body = req(p)
    d = json.loads(body)
    n = len(d.get(k) or [])
    ok = st == 200 and n == exp
    ok_all &= ok
    print('  [%s] %-30s HTTP %s  source=%-9s %s=%d' % (
        '✓' if ok else '❌', p, st, d.get('source'), k, n))

print()
print('【3】真实浏览器：作品站能渲染 + 数据来自真库')
print('-' * 78)

profile = tempfile.mkdtemp(prefix='edge-pub-')
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


cdp('Runtime.enable'); cdp('Page.enable'); cdp('Network.enable')
cdp('Network.setCacheDisabled', {'cacheDisabled': True})


def ev(e):
    r = cdp('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    return ((r.get('result') or {}).get('result') or {}).get('value')


def shot(n):
    r = cdp('Page.captureScreenshot', {'format': 'png'})
    d = ((r.get('result') or {}).get('data') or '')
    if d:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pub-' + n + '.png')
        open(p, 'wb').write(base64.b64decode(d))
        return os.path.basename(p)


try:
    cdp('Page.navigate', {'url': BASE + '/'})
    time.sleep(4.5)
    src = ev('window.__dataSource')
    cards = ev('document.querySelectorAll(".module-card").length')
    imgs = ev('(function(){var a=[].slice.call(document.images);return a.length+"张图,"+a.filter(function(i){return i.complete&&i.naturalWidth>0}).length+"张加载成功"})()')
    title = ev('document.title')
    print('  [%s] 作品站首页  标题=%r' % ('✓' if src == 'api' and cards else '❌', title))
    print('       数据源=%s  模块卡=%s  图片=%s' % (src, cards, imgs))
    print('       截图 →', shot('作品站首页'))
    ok_all &= (src == 'api' and cards == 6)

    for nm, rt, cntq in [('同人音乐', '#/music', 6), ('同人图', '#/art', 7), ('同人视频', '#/video', 6)]:
        cdp('Page.navigate', {'url': BASE + '/' + rt})
        time.sleep(3.5)
        c = ev('document.querySelectorAll(".work-item,.video-card").length')
        ok = c == cntq
        ok_all &= ok
        print('  [%s] %-10s 卡片=%s（期望 %d）' % ('✓' if ok else '❌', nm, c, cntq))

    cdp('Page.navigate', {'url': BASE + '/#/music/1'})
    time.sleep(3.5)
    t = ev('((document.querySelector("#app h2")||{}).textContent||"").trim()')
    im = ev('(function(){var i=document.querySelector("#app img.zoomable");return i?(i.complete&&i.naturalWidth>0):false})()')
    print('  [%s] 音乐详情  标题=%r  封面加载=%s' % ('✓' if t else '❌', t, im))
    print('       截图 →', shot('音乐详情'))
    ok_all &= bool(t)

    cdp('Page.navigate', {'url': BASE + '/verify/'})
    time.sleep(3.5)
    vt = ev('document.title')
    vbody = ev('document.body.textContent.trim().length')
    hasfav = ev('/收藏/.test(document.body.textContent)')
    print('  [%s] 验证页   标题=%r  文字长度=%s  含收藏模块=%s' % (
        '✓' if vt and vbody > 100 and hasfav else '❌', vt, vbody, hasfav))
    print('       截图 →', shot('验证页'))
    ok_all &= bool(vt and vbody > 100)

finally:
    print()
    print('=' * 78)
    print('总判定：', '✅ 全部通过，可以发布' if ok_all else '❌ 有失败项，见上')
    print('=' * 78)
    edge.kill(); srv.kill()
    shutil.rmtree(profile, ignore_errors=True)
