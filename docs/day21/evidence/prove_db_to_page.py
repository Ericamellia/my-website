# -*- coding: utf-8 -*-
"""核心需求验证：改数据库里的数据 → 网站页面立刻能看到变化。

流程：
  1. 读当前 music-1 的 name（原值）
  2. 用 REST PATCH 改成一个临时标记值
  3. 起服务 + 浏览器，打开页面，断言看到的是新值
  4. 改回原值，再断言恢复
全程用 PATCH 只改 name 一个字段，测完必须还原（脚本里用 try/finally 保证）。
"""
import json, urllib.request, os, subprocess, sys, io, time, socket, base64, shutil, tempfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 8090
CDP_PORT = 9234
BASE = 'http://127.0.0.1:%d' % PORT

ENV = {}
with open(os.path.join(ROOT, '.env'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")

REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % ENV['CLOUDBASE_ENV_ID']
KEY = ENV['CLOUDBASE_API_KEY']


def rest(method, table, query='', body=None, prefer=None):
    url = REST + table + ('?' + query if query else '')
    h = {'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
    if prefer:
        h['Prefer'] = prefer
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=25) as r:
        txt = r.read().decode('utf-8')
        return r.status, (json.loads(txt) if txt.strip() else None)


# ---- 1. 读原值 ----
_, rows = rest('GET', 'works', 'select=work_id,name&work_id=eq.music-1')
ORIG = rows[0]['name']
MARK = '★数据库改的★'
print('=' * 76)
print('核心需求验证：改库 → 网站页面立刻变化')
print('=' * 76)
print('原值        :', ORIG)

os.environ.update(ENV)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(k, None)

link = os.path.join(DEPLOY, 'public', '_myapp_test')
srv = edge = profile = None
changed = False

try:
    # ---- 2. 改库 ----
    st, _ = rest('PATCH', 'works', 'work_id=eq.music-1', {'name': MARK}, 'return=minimal')
    changed = True
    time.sleep(1.2)
    _, rows2 = rest('GET', 'works', 'select=name&work_id=eq.music-1')
    print('改库后读回  :', rows2[0]['name'], ' (PATCH 状态 %s)' % st)

    # ---- 3. 起服务 + 浏览器看页面 ----
    shutil.rmtree(link, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, 'my-app'), link, ignore=shutil.ignore_patterns('.workbuddy'))
    srv = subprocess.Popen([NODE, 'server.js'], cwd=DEPLOY, env=dict(os.environ, PORT=str(PORT)),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            socket.create_connection(('127.0.0.1', PORT), timeout=1).close(); break
        except Exception:
            time.sleep(0.3)

    profile = tempfile.mkdtemp(prefix='edge-db-')
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

    rest_ws = target['webSocketDebuggerUrl'][5:]
    hp, _, path = rest_ws.partition('/')
    host, _, port = hp.partition(':')
    sk = socket.create_connection((host, int(port)), timeout=25)
    kk = base64.b64encode(os.urandom(16)).decode()
    sk.sendall(('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (path, hp, kk)).encode())
    b = b''
    while b'\r\n\r\n' not in b:
        b += sk.recv(4096)
    cnt = [0]

    def cdpsend(d):
        p = d.encode(); m = os.urandom(4); n = len(p)
        h = bytearray([0x81])
        if n < 126:
            h.append(0x80 | n)
        elif n < 65536:
            h.append(0x80 | 126); h += struct.pack('>H', n)
        else:
            h.append(0x80 | 127); h += struct.pack('>Q', n)
        h += m
        sk.sendall(bytes(h) + bytes(x ^ m[i % 4] for i, x in enumerate(p)))

    def cdprecv():
        def rd(n):
            d = b''
            while len(d) < n:
                c = sk.recv(n - len(d))
                if not c: raise IOError('closed')
                d += c
            return d
        hh = rd(2); ln = hh[1] & 0x7F
        if ln == 126: ln = struct.unpack('>H', rd(2))[0]
        elif ln == 127: ln = struct.unpack('>Q', rd(8))[0]
        return rd(ln).decode('utf-8', 'ignore')

    def cdp(method, params=None):
        cnt[0] += 1; mid = cnt[0]
        cdpsend(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        while True:
            m = json.loads(cdprecv())
            if m.get('id') == mid:
                return m

    # 强制硬刷新：先 about:blank + 清缓存，确保拿到的是新数据（而不是 dataPromise 内存缓存）
    cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})
    cdp('Page.navigate', {'url': 'about:blank'})
    time.sleep(0.8)
    cdp('Page.navigate', {'url': BASE + '/_myapp_test/index.html#/music/1'})
    time.sleep(4.5)

    def ev(e):
        r = cdp('Runtime.evaluate', {'expression': e, 'returnByValue': True})
        return ((r.get('result') or {}).get('result') or {}).get('value')

    shown = ev('((document.querySelector("#app h2")||{}).textContent||"").trim()')
    src = ev('window.__dataSource')
    print()
    print('页面显示    :', shown, '   (数据源 %s)' % src)
    print('→ 页面看到了改后的值 ?', '✅ 是' if shown == MARK else '❌ 否')

    # ---- 4. 还原 ----
    rest('PATCH', 'works', 'work_id=eq.music-1', {'name': ORIG}, 'return=minimal')
    changed = False
    time.sleep(1.2)
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.8)
    cdp('Page.navigate', {'url': BASE + '/_myapp_test/index.html#/music/1'})
    time.sleep(4.5)
    back = ev('((document.querySelector("#app h2")||{}).textContent||"").trim()')
    print()
    print('还原后页面  :', back)
    print('→ 恢复成原值 ?', '✅ 是' if back == ORIG else '❌ 否')

    _, rows3 = rest('GET', 'works', 'select=name&work_id=eq.music-1')
    print('库里最终值  :', rows3[0]['name'])
    print()
    print('=' * 76)
    print('结论：', '✅ 改数据库 → 网站立刻可见（这是「作品内容存在数据库」的直接证明）'
          if shown == MARK and back == ORIG else '❌ 未达预期')
    print('=' * 76)

finally:
    if changed:
        rest('PATCH', 'works', 'work_id=eq.music-1', {'name': ORIG}, 'return=minimal')
        print('\n⚠️ 已强制还原数据库')
    if edge: edge.kill()
    if srv: srv.kill()
    if profile: shutil.rmtree(profile, ignore_errors=True)
    shutil.rmtree(link, ignore_errors=True)
