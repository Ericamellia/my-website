# -*- coding: utf-8 -*-
"""抓页面控制台日志和 JS 异常，定位为什么 __dataSource 未设置。"""
import json, urllib.request, os, subprocess, sys, io, time, socket, base64, tempfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
CDP_PORT = 9232
URL = 'http://127.0.0.1:8092/_myapp_test/'

profile = tempfile.mkdtemp(prefix='edge-log-')
edge = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, 'about:blank'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

target = None
for _ in range(40):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
            pages = [t for t in json.loads(r.read().decode()) if t.get('type') == 'page']
        if pages:
            target = pages[0]; break
    except Exception:
        pass
    time.sleep(0.5)

ws = target['webSocketDebuggerUrl']
rest = ws[5:]
hostport, _, path = rest.partition('/')
host, _, port = hostport.partition(':')
s = socket.create_connection((host, int(port)), timeout=25)
key = base64.b64encode(os.urandom(16)).decode()
s.sendall(('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
           'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (path, hostport, key)).encode())
buf = b''
while b'\r\n\r\n' not in buf:
    buf += s.recv(4096)


def send(data):
    payload = data.encode(); mask = os.urandom(4); n = len(payload)
    h = bytearray([0x81])
    if n < 126:
        h.append(0x80 | n)
    elif n < 65536:
        h.append(0x80 | 126); h += struct.pack('>H', n)
    else:
        h.append(0x80 | 127); h += struct.pack('>Q', n)
    h += mask
    s.sendall(bytes(h) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def recv():
    def rd(n):
        d = b''
        while len(d) < n:
            c = s.recv(n - len(d))
            if not c: raise IOError('closed')
            d += c
        return d
    h = rd(2); ln = h[1] & 0x7F
    if ln == 126: ln = struct.unpack('>H', rd(2))[0]
    elif ln == 127: ln = struct.unpack('>Q', rd(8))[0]
    return rd(ln).decode('utf-8', 'ignore')


mid = [0]
events = []


def call(method, params=None):
    mid[0] += 1
    send(json.dumps({'id': mid[0], 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(recv())
        if m.get('id') == mid[0]:
            return m
        if 'method' in m:
            events.append(m)


call('Runtime.enable')
call('Page.enable')
call('Log.enable')
call('Network.enable')
call('Page.navigate', {'url': URL})
time.sleep(6)

# 收事件
s.settimeout(1)
try:
    while True:
        m = json.loads(recv())
        if 'method' in m:
            events.append(m)
except Exception:
    pass

print('=' * 78)
print('页面事件（控制台 / 异常 / 失败请求）')
print('=' * 78)
for e in events:
    m = e.get('method')
    p = e.get('params') or {}
    if m == 'Runtime.consoleAPICalled':
        args = [str(a.get('value', a.get('description', '')))[:160] for a in (p.get('args') or [])]
        print('[console.%s] %s' % (p.get('type'), ' | '.join(args)))
    elif m == 'Runtime.exceptionThrown':
        d = (p.get('exceptionDetails') or {})
        print('[异常] %s  @line %s' % (d.get('text'), d.get('lineNumber')))
        ex = d.get('exception') or {}
        if ex.get('description'):
            print('        ', ex['description'][:300])
    elif m == 'Network.loadingFailed':
        print('[请求失败] %s %s' % (p.get('type'), p.get('errorText')))
    elif m == 'Log.entryAdded':
        en = p.get('entry') or {}
        print('[log.%s] %s' % (en.get('level'), str(en.get('text'))[:200]))

print()
r = call('Runtime.evaluate', {'expression': 'JSON.stringify({src: window.__dataSource||null, cards: document.querySelectorAll(".work-item,.video-card,.og-card,.module-card").length, appLen: (document.getElementById("app")||{}).innerHTML ? document.getElementById("app").innerHTML.length : 0})', 'returnByValue': True})
print('最终状态:', json.dumps(r.get('result', {}), ensure_ascii=False)[:300])

edge.kill()
