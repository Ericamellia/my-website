# -*- coding: utf-8 -*-
"""
用 CDP 真实记录页面网络请求，并用 Page.captureScreenshot 截图。
用法: python cdp_net.py <url> <输出png> [额外等待秒]
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PROFILE = r'C:\Users\25394\shots\edge-cdp'
PORT = 9333

url = sys.argv[1]
out = sys.argv[2]
extra = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0

env = dict(os.environ)
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
    env.pop(k, None)

subprocess.Popen([EDGE, '--start-maximized', '--new-window',
                  '--user-data-dir=' + PROFILE, '--no-first-run',
                  '--no-default-browser-check',
                  '--remote-debugging-port=%d' % PORT,
                  '--remote-allow-origins=*', url],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
page = None
for _ in range(30):
    time.sleep(1)
    try:
        targets = json.loads(op.open('http://127.0.0.1:%d/json' % PORT, timeout=5).read().decode())
    except Exception:
        continue
    for t in targets:
        if t.get('type') == 'page' and 'workbuddy.host' in t.get('url', ''):
            page = t
            break
    if page:
        break
if not page:
    print('page not found')
    sys.exit(1)
print('PAGE:', page['url'])

ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=20,
                                 http_proxy_host=None)
mid = [0]
pending = {}


def send(method, params=None):
    mid[0] += 1
    ws.send(json.dumps({'id': mid[0], 'method': method, 'params': params or {}}))
    return mid[0]


send('Network.enable')
send('Page.enable')
send('Page.reload', {'ignoreCache': True})

records = []
inflight = {}
deadline = time.time() + 20
while time.time() < deadline:
    try:
        ws.settimeout(2.5)
        raw = ws.recv()
    except Exception:
        continue
    try:
        msg = json.loads(raw)
    except Exception:
        continue
    m = msg.get('method')
    p = msg.get('params', {})
    if m == 'Network.requestWillBeSent':
        rid = p.get('requestId')
        inflight[rid] = {'method': p['request']['method'], 'url': p['request']['url']}
    elif m == 'Network.responseReceived':
        rid = p.get('requestId')
        r = p.get('response', {})
        rec = inflight.get(rid, {})
        records.append({
            'method': rec.get('method', 'GET'),
            'url': r.get('url', rec.get('url')),
            'status': r.get('status'),
            'type': p.get('type'),
            'remote': (r.get('remoteIPAddress') or ''),
        })

print('\n=== NETWORK (API only) ===')
for r in records:
    u = r['url'] or ''
    if '/api/' in u:
        print('%s %s -> %s  [%s]' % (r['method'], u, r['status'], r['remote']))

time.sleep(extra)

# 截图
sid = send('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
shot = None
dl = time.time() + 12
while time.time() < dl:
    try:
        ws.settimeout(2)
        raw = ws.recv()
    except Exception:
        continue
    msg = json.loads(raw)
    if msg.get('id') == sid:
        shot = msg.get('result', {}).get('data')
        break
if shot:
    with open(out, 'wb') as f:
        f.write(base64.b64decode(shot))
    print('saved', out)
else:
    print('screenshot failed')
