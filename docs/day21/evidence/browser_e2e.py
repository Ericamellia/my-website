# -*- coding: utf-8 -*-
"""真实浏览器端到端验证（自起服务 + 自起浏览器，一个进程跑完）。

证明：my-app 页面的作品内容确实来自数据库接口，且各功能页面正常渲染。
产出：控制台截图 + 逐页卡片数。
"""
import json, urllib.request, os, subprocess, sys, io, time, socket, base64, shutil, tempfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 8091
CDP_PORT = 9233
BASE = 'http://127.0.0.1:%d' % PORT

ENV = dict(os.environ)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    ENV.pop(k, None)

# 1) 把 my-app 拷到 Node 静态目录（Windows 下 os.symlink 需要管理员权限，故用真实拷贝）
link = os.path.join(DEPLOY, 'public', '_myapp_test')
shutil.rmtree(link, ignore_errors=True)
shutil.copytree(os.path.join(ROOT, 'my-app'), link,
                ignore=shutil.ignore_patterns('.workbuddy'))

# 2) 起 Node 服务
srv = subprocess.Popen([NODE, 'server.js'], cwd=DEPLOY, env=dict(ENV, PORT=str(PORT)),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
up = False
for _ in range(60):
    try:
        socket.create_connection(('127.0.0.1', PORT), timeout=1).close()
        up = True; break
    except Exception:
        time.sleep(0.3)
if not up:
    print('❌ Node 服务未起来'); srv.kill(); sys.exit(1)
print('✓ Node 服务已启动 :%d' % PORT)

# 3) 起 Edge
profile = tempfile.mkdtemp(prefix='edge-e2e-')
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
if not target:
    print('❌ Edge CDP 未就绪'); edge.kill(); srv.kill(); sys.exit(1)
print('✓ Edge 已启动 (CDP :%d)' % CDP_PORT)


class CDP:
    def __init__(self, url):
        rest = url[5:]
        hp, _, path = rest.partition('/')
        host, _, port = hp.partition(':')
        self.s = socket.create_connection((host, int(port)), timeout=25)
        k = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n'
                        % (path, hp, k)).encode())
        b = b''
        while b'\r\n\r\n' not in b:
            b += self.s.recv(4096)
        self.i = 0

    def send(self, d):
        p = d.encode(); m = os.urandom(4); n = len(p)
        h = bytearray([0x81])
        if n < 126:
            h.append(0x80 | n)
        elif n < 65536:
            h.append(0x80 | 126); h += struct.pack('>H', n)
        else:
            h.append(0x80 | 127); h += struct.pack('>Q', n)
        h += m
        self.s.sendall(bytes(h) + bytes(x ^ m[i % 4] for i, x in enumerate(p)))

    def recv(self):
        def rd(n):
            d = b''
            while len(d) < n:
                c = self.s.recv(n - len(d))
                if not c: raise IOError('closed')
                d += c
            return d
        h = rd(2); ln = h[1] & 0x7F
        if ln == 126: ln = struct.unpack('>H', rd(2))[0]
        elif ln == 127: ln = struct.unpack('>Q', rd(8))[0]
        return rd(ln).decode('utf-8', 'ignore')

    def call(self, method, params=None):
        self.i += 1; mid = self.i
        self.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        self.last_events = []
        while True:
            m = json.loads(self.recv())
            if m.get('id') == mid:
                return m
            if 'method' in m:
                self.last_events.append(m)


cdp = CDP(target['webSocketDebuggerUrl'])
cdp.call('Runtime.enable')
cdp.call('Page.enable')
cdp.call('Network.enable')
cdp.call('Emulation.setDeviceMetricsOverride',
         {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})

RESULTS = []


def ev(expr):
    r = cdp.call('Runtime.evaluate',
                 {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
    res = (r.get('result') or {}).get('result') or {}
    return res.get('value')


def shot(name):
    r = cdp.call('Page.captureScreenshot', {'format': 'png'})
    d = ((r.get('result') or {}).get('data') or '')
    if d:
        p = os.path.join(OUTDIR, 'myapp-' + name + '.png')
        open(p, 'wb').write(base64.b64decode(d))
        return os.path.basename(p)
    return None


def visit(name, route, checks, snap=False):
    url = BASE + '/_myapp_test/index.html' + (('#' + route[1:]) if route else '')
    cdp.call('Page.navigate', {'url': url})
    time.sleep(3.5)
    print('\n' + '-' * 76)
    print('【%s】 %s' % (name, route or '/'))
    src = ev('window.__dataSource || "(未设置)"')
    print('  数据来源 =', src)
    if snap:
        f = shot(name)
        print('  截图 →', f)
    for label, expr in checks:
        v = ev(expr)
        ok = v is not None and v is not False and v != '' and v != 0
        RESULTS.append((name, label, ok, v))
        print('  [%s] %-24s → %s' % ('✓' if ok else '❌', label,
                                     json.dumps(v, ensure_ascii=False)[:110] if not isinstance(v, str) else v[:110]))
    return src


try:
    print()
    print('=' * 76)
    print('真实浏览器端到端验证：my-app 页面 ← 真库接口')
    print('=' * 76)
    visit('首页', '', [('数据源', 'window.__dataSource'),
                       ('页面上有模块卡', 'document.querySelectorAll(".module-card").length')], snap=True)

    for nm, rt in [('同人音乐', '#/music'), ('同人漫画', '#/doujin'), ('同人游戏', '#/game'),
                   ('同人视频', '#/video'), ('同人图', '#/art')]:
        visit(nm, rt, [('卡片数', 'document.querySelectorAll(".work-item,.video-card,.og-card").length')])

    visit('原作作品页(ZUN原曲)', '#/original',
          [('原作卡片数', 'document.querySelectorAll(".og-card").length')], snap=True)

    visit('收藏页', '#/fav',
          [('页面文字长度', 'document.getElementById("app").textContent.trim().length')])

    visit('上传作品页', '#/add',
          [('页面文字长度', 'document.getElementById("app").textContent.trim().length')])

    visit('音乐详情', '#/music/1',
          [('详情标题', '((document.querySelector("h1")||{}).textContent||"").trim()'),
           ('操作按钮数', 'document.querySelectorAll(".detail-cta").length')], snap=True)

    visit('视频详情', '#/video/1',
          [('详情标题', '((document.querySelector("h1")||{}).textContent||"").trim()'),
           ('B站链接', '(function(){var a=[].slice.call(document.querySelectorAll("a")).filter(function(x){return /bilibili\\.com\\/video/.test(x.href)});return a.length?a[0].href:""})()')])

    visit('角色反查', '#/character/博丽灵梦',
          [('页面文字长度', 'document.getElementById("app").textContent.trim().length')], snap=True)

    visit('社团页', '#/circle/A-One',
          [('页面文字长度', 'document.getElementById("app").textContent.trim().length')])

    visit('搜索页', '#/search/灵梦',
          [('搜索结果数', 'document.querySelectorAll(".work-item,.video-card").length')])

    # 顺带：确认接口是数据来源（不是本地 JSON）
    print()
    print('=' * 76)
    print('数据来源交叉验证')
    print('=' * 76)
    cdp.call('Page.navigate', {'url': BASE + '/_myapp_test/index.html#/music'})
    time.sleep(3.5)
    print('  window.__dataSource =', ev('window.__dataSource'))
    print('  window.data.music[0].name =', ev('window.data ? window.data.music[0].name : "(data 不在 window 上)"'))
    print('  window.data.video[0].url =', ev('window.data ? window.data.video[0].url : ""'))

finally:
    print()
    print('=' * 76)
    bad = [r for r in RESULTS if not r[2]]
    print('汇总：检查 %d 项，通过 %d，失败 %d' % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    for n, l, ok, v in bad:
        print('  ❌ %s / %s → %s' % (n, l, v))
    edge.kill(); srv.kill()
    shutil.rmtree(profile, ignore_errors=True)
    shutil.rmtree(link, ignore_errors=True)
    print('（已清理）')
