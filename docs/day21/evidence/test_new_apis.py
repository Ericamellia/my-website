# -*- coding: utf-8 -*-
"""Day 21 路线B 第2件：自起服务 + 实测 5 个新接口（走真库 REST 通道）。"""
import json, urllib.request, os, subprocess, sys, io, time, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
PORT = 8097
BASE = 'http://127.0.0.1:%d' % PORT

# 清掉代理（否则本地请求会被代理拦截返回 502）
ENV = dict(os.environ)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    ENV.pop(k, None)

proc = subprocess.Popen(
    [NODE, 'server.js'],
    cwd=DEPLOY, env=dict(ENV, PORT=str(PORT)),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)


def wait_up(timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(('127.0.0.1', PORT), timeout=1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


if not wait_up():
    print('❌ 服务未能启动')
    proc.kill()
    print(proc.stdout.read().decode('utf-8', 'ignore')[:2000])
    sys.exit(1)


def get(path):
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {'__raw__': e.read().decode('utf-8', 'ignore')[:200]}
    except Exception as e:
        return -1, {'__error__': str(e)}


def check(label, path, expect_count=None, list_key='data'):
    st, d = get(path)
    n = None
    if isinstance(d, dict) and '__error__' not in d:
        if list_key and isinstance(d.get(list_key), list):
            n = len(d[list_key])
        elif d.get('count') is not None:
            n = d.get('count')
    mark = ''
    if expect_count is not None:
        mark = '   ✓' if n == expect_count else '   ❌ 期望 %s' % expect_count
    print('%-38s HTTP %-4s source=%-9s count=%-4s%s' % (
        label, st, (d.get('source') if isinstance(d, dict) else '?'), n, mark))

    if isinstance(d, dict) and '__error__' not in d:
        first = None
        for k in [list_key, 'characters', 'games']:
            if isinstance(d.get(k), list) and d[k]:
                first = d[k][0]
                break
        if first:
            print('      字段:', ', '.join(sorted(first.keys())))
            print('      样例:', json.dumps(first, ensure_ascii=False)[:230])
    elif isinstance(d, dict):
        print('      返回:', json.dumps(d, ensure_ascii=False)[:230])
    print()
    return d


print('=' * 78)
print('Day 21 路线B 第2件：5 个新接口实测（真库 REST 通道）')
print('=' * 78)
print()

d_music = check('/api/works?category=music', '/api/works?category=music', 6)
check('/api/works?category=art', '/api/works?category=art', 7)
check('/api/works?category=video', '/api/works?category=video', 6)
check('/api/works（不带 category）', '/api/works', 30)
check('/api/works?category=xxx（非法值）', '/api/works?category=xxx', None)
check('/api/circles', '/api/circles', 26)
d_og = check('/api/original-games', '/api/original-games', None, list_key='games')
check('/api/characters', '/api/characters', 112, list_key='characters')
check('/api/originals', '/api/originals', 6)

print('=' * 78)
print('附加核对：id 拆解 + 与本地 JSON 逐字段一致性')
print('=' * 78)
st, d = get('/api/works?category=music')
if st == 200:
    api_ids = [x['id'] for x in d['data']]
    api_wids = [x['workId'] for x in d['data']]
    local = json.load(open(os.path.join(ROOT, 'my-app', 'data', 'music.json'), encoding='utf-8'))
    local_ids = [x['id'] for x in local]
    print('接口返回的数字 id :', api_ids)
    print('接口返回的 workId  :', api_wids)
    print('本地 JSON 的 id    :', local_ids)
    print('→ id 一致吗？', api_ids == local_ids)

    # 逐字段比第一条（除 id 外的关键字段）
    if d['data'] and local:
        a, b = d['data'][0], local[0]
        keys = ['name', 'circle', 'creator', 'year', 'cover', 'source_url', 'description']
        print()
        print('第 1 条逐字段对比（接口 vs 本地 JSON）：')
        for k in keys:
            same = '✓' if a.get(k) == b.get(k) else '❌'
            print('  %-12s %s  接口=%-46s 本地=%s' % (k, same, str(a.get(k))[:46], str(b.get(k))[:40]))

if d_og and isinstance(d_og, dict):
    print()
    print('original-games 的 categories:', json.dumps(d_og.get('categories'), ensure_ascii=False))
    print('original-games 的 games 条数:', len(d_og.get('games') or []))

proc.kill()
print()
print('（本地服务已关闭）')
