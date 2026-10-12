# -*- coding: utf-8 -*-
"""排查第 3 层：Node 服务接口是否把新值带出来。"""
import json, urllib.request, os, subprocess, sys, io, time, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
PORT = 8089

ENV = {}
for line in open(os.path.join(ROOT, '.env'), encoding='utf-8'):
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    ENV[k.strip()] = v.strip().strip('"').strip("'")

REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % ENV['CLOUDBASE_ENV_ID']
KEY = ENV['CLOUDBASE_API_KEY']


def rest(m, t, q='', b=None, prefer=None):
    h = {'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
    if prefer:
        h['Prefer'] = prefer
    d = json.dumps(b).encode() if b is not None else None
    r = urllib.request.Request(REST + t + ('?' + q if q else ''), data=d, headers=h, method=m)
    with urllib.request.urlopen(r, timeout=25) as x:
        tx = x.read().decode()
        return x.status, (json.loads(tx) if tx.strip() else None)


E = dict(os.environ)
E.update(ENV)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    E.pop(k, None)

srv = subprocess.Popen([NODE, 'server.js'], cwd=DEPLOY, env=dict(E, PORT=str(PORT)),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(60):
    try:
        socket.create_connection(('127.0.0.1', PORT), timeout=1).close(); break
    except Exception:
        time.sleep(0.3)

ORIG = 'ハルトマンの妖怪少女'
MARK = '★接口测试★'


def api():
    req = urllib.request.Request('http://127.0.0.1:%d/api/works?category=music' % PORT)
    with urllib.request.urlopen(req, timeout=20) as x:
        d = json.loads(x.read().decode())
    return d['data'][0]['name'], d.get('source')


try:
    print('=' * 70)
    print('第 3 层排查：Node 服务 /api/works 是否带出新值')
    print('=' * 70)
    print()
    print('改库前 → 接口返回:', api())
    rest('PATCH', 'works', 'work_id=eq.music-1', {'name': MARK}, 'return=minimal')
    time.sleep(1.5)
    print('改库后 → 接口返回:', api())
    time.sleep(2)
    print('再等 2 秒 → 接口返回:', api())
    print()
    print('直接读库      :', rest('GET', 'works', 'select=name&work_id=eq.music-1')[1][0]['name'])
finally:
    rest('PATCH', 'works', 'work_id=eq.music-1', {'name': ORIG}, 'return=minimal')
    time.sleep(1)
    print()
    print('已还原:', rest('GET', 'works', 'select=name&work_id=eq.music-1')[1][0]['name'])
    srv.kill()
