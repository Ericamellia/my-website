# -*- coding: utf-8 -*-
"""验证 5 个新接口的「快照降级通道」。
做法：临时把 .env 挪走（服务就找不到凭证）→ 应降级到 snapshot → 测完恢复。
这样能证明：真库连不上时接口不会崩，而是落到本地 JSON 快照继续服务。
"""
import json, urllib.request, os, subprocess, sys, io, time, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
PORT = 8096
BASE = 'http://127.0.0.1:%d' % PORT

# .env 可能在这些位置
env_files = [os.path.join(DEPLOY, '.env'), os.path.join(ROOT, '.env')]
moved = []
for p in env_files:
    if os.path.exists(p):
        tmp = p + '.testhidden'
        os.replace(p, tmp)
        moved.append((p, tmp))
        print('已临时移走:', p)

ENV = dict(os.environ)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy',
          'CLOUDBASE_ENV_ID', 'CLOUDBASE_API_KEY', 'PG_URL', 'DATABASE_URL']:
    ENV.pop(k, None)

proc = None
try:
    proc = subprocess.Popen([NODE, 'server.js'], cwd=DEPLOY,
                            env=dict(ENV, PORT=str(PORT)),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(('127.0.0.1', PORT), timeout=1).close()
            break
        except Exception:
            time.sleep(0.3)

    def get(path):
        try:
            with urllib.request.urlopen(BASE + path, timeout=20) as r:
                return r.status, json.loads(r.read().decode('utf-8'))
        except Exception as e:
            return -1, {'__error__': str(e)}

    print()
    print('=' * 72)
    print('快照降级通道验证（.env 已移走 → 服务应降级到 snapshot）')
    print('=' * 72)
    st, h = get('/api/health')
    print('健康检查 dataSource =', (h.get('checks') or {}).get('dataSource'),
          '  <- 期望 snapshot')
    print()

    cases = [
        ('/api/works?category=music', 'data', 6),
        ('/api/circles', 'data', 26),
        ('/api/original-games', 'games', 39),
        ('/api/characters', 'characters', 112),
        ('/api/originals', 'data', 6),
    ]
    for path, key, exp in cases:
        st, d = get(path)
        n = len(d.get(key) or []) if isinstance(d, dict) else None
        mark = '✓' if n == exp else '❌ 期望 %s' % exp
        print('%-30s HTTP %-4s source=%-9s count=%-4s %s' % (
            path, st, (d.get('source') if isinstance(d, dict) else '?'), n, mark))
finally:
    if proc:
        proc.kill()
    for p, tmp in moved:
        os.replace(tmp, p)
        print('已恢复:', p)

print()
print('（降级服务已关闭，.env 已还原）')
