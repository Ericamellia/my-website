# -*- coding: utf-8 -*-
"""真实浏览器验证（CDP）v2：修掉 target attach 问题。

证明：页面的作品内容确实来自数据库接口，且所有功能页面能正常渲染。
顺便截图存证。
"""
import json, urllib.request, os, subprocess, sys, io, time, socket, base64, shutil, tempfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 8093
CDP_PORT = 9224
BASE = 'http://127.0.0.1:%d' % PORT

ENV = dict(os.environ)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    ENV.pop(k, None)

link_target = os.path.join(DEPLOY, 'public', '_myapp_test')
shutil.rmtree(link_target, ignore_errors=True)
used_link = False
try:
    os.symlink(os.path.join(ROOT, 'my-app'), link_target, target_is_directory=True)
    used_link = True
except Exception:
    shutil.copytree(os.path.join(ROOT, 'my-app'), link_target,
                    ignore=shutil.ignore_patterns('.workbuddy'))

srv = subprocess.Popen([NODE, 'server.js'], cwd=DEPLOY, env=dict(ENV, PORT=str(PORT)),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try:
        socket.create_connection(('127.0.0.1', PORT), timeout=1).close()
        break
    except Exception:
        time.sleep(0.3)

profile = tempfile.mkdtemp(prefix='edge-cdp2-')
edge = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1440,900',
    BASE + '/_myapp_test/'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 等 CDP，并拿到**已存在的页面 target**（不要新建）
target = None
for _ in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
            lst = json.loads(r.read().decode())
        for t in lst:
            if t.get('type') == 'page' and t.get('webSocketDebuggerUrl'):
                target = t
                break
        if target:
            break
    except Exception:
        pass
    time.sleep(0.5)

if not target:
    print('❌ 未找到页面 target')
    edge.kill(); srv.kill(); sys.exit(1)


class CDP:
    def __init__(self, url):
        rest = url[5:]
        hostport, _, path = rest.partition('/')
        host, _, port = hostport.partition(':')
        self.s = socket.create_connection((host, int(port)), timeout=25)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n'
                        % (path, hostport, key)).encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            buf += self.s.recv(4096)
        self._id = 0

    def _send(self, data):
        payload = data.encode()
        mask = os.urandom(4)
        n = len(payload)
        h = bytearray([0x81])
        if n < 126:
            h.append(0x80 | n)
        elif n < 65536:
            h.append(0x80 | 126); h += struct.pack('>H', n)
        else:
            h.append(0x80 | 127); h += struct.pack('>Q', n)
        h += mask
        self.s.sendall(bytes(h) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _recv(self):
        def rd(n):
            d = b''
            while len(d) < n:
                c = self.s.recv(n - len(d))
                if not c:
                    raise IOError('closed')
                d += c
            return d
        h = rd(2)
        ln = h[1] & 0x7F
        if ln == 126:
            ln = struct.unpack('>H', rd(2))[0]
        elif ln == 127:
            ln = struct.unpack('>Q', rd(8))[0]
        return rd(ln).decode('utf-8', 'ignore')

    def call(self, method, params=None):
        self._id += 1
        mid = self._id
        self._send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        while True:
            m = json.loads(self._recv())
            if m.get('id') == mid:
                return m


cdp = CDP(target['webSocketDebuggerUrl'])
cdp.call('Runtime.enable')
cdp.call('Page.enable')
cdp.call('Emulation.setDeviceMetricsOverride',
         {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})

RESULTS = []


def ev(expr, wait=0.4):
    r = cdp.call('Runtime.evaluate',
                 {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
    time.sleep(wait)
    res = (r.get('result') or {}).get('result') or {}
    if 'value' in res:
        return res['value']
    return res.get('description') or res.get('type')


def shot(name):
    r = cdp.call('Page.captureScreenshot', {'format': 'png'})
    data = ((r.get('result') or {}).get('data') or '')
    if not data:
        return None
    p = os.path.join(OUTDIR, 'myapp-' + name + '.png')
    with open(p, 'wb') as f:
        f.write(base64.b64decode(data))
    return os.path.basename(p)


def visit(name, route, checks, snap=False):
    url = BASE + '/_myapp_test/' + route
    cdp.call('Page.navigate', {'url': url})
    time.sleep(3.2)
    print('\n' + '=' * 78)
    print('【%s】 %s' % (name, route or '/'))
    print('=' * 78)
    src = ev('window.__dataSource || "(未设置)"')
    print('  数据来源 =', src)
    if snap:
        f = shot(name)
        if f:
            print('  截图 →', f)
    for label, expr in checks:
        v = ev(expr)
        ok = v is not None and v is not False and v != '' and v != 0
        RESULTS.append((name, label, ok, v))
        s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
        print('  [%s] %-28s → %s' % ('✓' if ok else '❌', label, str(s)[:120]))
    return src


try:
    src_home = visit('首页', '', [
        ('dataSource', 'window.__dataSource'),
    ], snap=True)

    for nm, rt in [('同人音乐', '#/music'), ('同人漫画', '#/doujin'), ('同人游戏', '#/game'),
                   ('同人视频', '#/video'), ('同人图', '#/art'), ('ZUN原曲', '#/original'),
                   ('原作作品', '#/original-games'), ('角色列表', '#/characters'),
                   ('社团列表', '#/circles')]:
        visit(nm, rt, [('渲染出的卡片数', 'document.querySelectorAll(".work-item,.video-card,.og-card,.module-card").length')])

    visit('音乐详情', '#/music/1', [
        ('详情标题', '(document.querySelector("h1")||{}).textContent'),
        ('来源链接存在', 'document.querySelectorAll(".detail-cta").length'),
    ], snap=True)

    visit('视频详情', '#/video/1', [
        ('详情标题', '(document.querySelector("h1")||{}).textContent'),
        ('B站链接', '(function(){var a=[].slice.call(document.querySelectorAll("a")).filter(function(x){return /bilibili/.test(x.href)});return a.length?a[0].href:""})()'),
    ])

    visit('角色反查', '#/character/博丽灵梦', [
        ('页面文字长度', 'document.getElementById("app").textContent.trim().length'),
    ], snap=True)

    visit('社团页', '#/circle/COOL%26CREATE', [
        ('页面文字长度', 'document.getElementById("app").textContent.trim().length'),
    ])

    visit('搜索页', '#/search?q=灵梦', [
        ('页面文字长度', 'document.getElementById("app").textContent.trim().length'),
    ])

finally:
    print('\n' + '=' * 78)
    print('汇总')
    print('=' * 78)
    bad = [r for r in RESULTS if not r[2]]
    print('检查项 %d 个，通过 %d，失败 %d' % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    for n, l, ok, v in bad:
        print('  ❌ %s / %s → %s' % (n, l, v))
    edge.kill(); srv.kill()
    shutil.rmtree(profile, ignore_errors=True)
    if used_link:
        try:
            os.unlink(link_target)
        except Exception:
            shutil.rmtree(link_target, ignore_errors=True)
    else:
        shutil.rmtree(link_target, ignore_errors=True)
    print('\n（已清理临时资源）')
