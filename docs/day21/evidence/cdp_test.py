# -*- coding: utf-8 -*-
"""单独测 CDP：只打开页面读 window.__dataSource，验证 CDP 链路。"""
import json, urllib.request, os, subprocess, sys, io, time, socket, base64, tempfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
CDP_PORT = 9231
URL = 'http://127.0.0.1:8092/_myapp_test/'

profile = tempfile.mkdtemp(prefix='edge-t-')
edge = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, URL
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('Edge 已启动, pid=', edge.pid)

target = None
for i in range(40):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
            lst = json.loads(r.read().decode())
        pages = [t for t in lst if t.get('type') == 'page']
        if pages:
            target = pages[0]
            print('第 %d 次拿到 target: %s' % (i, target.get('url')))
            break
    except Exception as e:
        pass
    time.sleep(0.5)

if not target:
    print('❌ 拿不到 target')
    edge.kill(); sys.exit(1)

ws = target['webSocketDebuggerUrl']
print('ws =', ws)
rest = ws[5:]
hostport, _, path = rest.partition('/')
host, _, port = hostport.partition(':')
print('host=%s port=%s path=%s' % (host, port, path))

s = socket.create_connection((host, int(port)), timeout=25)
key = base64.b64encode(os.urandom(16)).decode()
s.sendall(('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
           'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n'
           % (path, hostport, key)).encode())
buf = b''
while b'\r\n\r\n' not in buf:
    buf += s.recv(4096)
print('握手完成:', buf.split(b'\r\n')[0].decode())


def send(data):
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
    s.sendall(bytes(h) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def recv():
    def rd(n):
        d = b''
        while len(d) < n:
            c = s.recv(n - len(d))
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


def call(method, params=None, mid=1):
    send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(recv())
        if m.get('id') == mid:
            return m


print('Runtime.enable →', json.dumps(call('Runtime.enable'), ensure_ascii=False)[:150])
time.sleep(2)
r = call('Runtime.evaluate', {'expression': 'window.__dataSource || "(未设置)"',
                              'returnByValue': True}, mid=2)
print('evaluate →', json.dumps(r, ensure_ascii=False)[:300])
r2 = call('Runtime.evaluate', {'expression': 'document.title + " | 卡片数=" + document.querySelectorAll(".work-item,.video-card,.og-card,.module-card").length',
                               'returnByValue': True}, mid=3)
print('页面状态 →', json.dumps(r2, ensure_ascii=False)[:300])

edge.kill()
