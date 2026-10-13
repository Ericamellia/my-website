# -*- coding: utf-8 -*-
"""
Day 24 板块④ 回归脚本 —— 修复后跑全接口，确认没改坏

做两件事：
  A. 跑 Day 22 的 CRUD 闭环脚本（增查改删 + 快照对比）
  B. 跑一组只读接口冒烟（8 个正常接口 + 错误路径）
起服务、跑测试、关服务都在一个进程里，避免后台进程被回收。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PORT = 3096
PY = sys.executable

env = dict(os.environ)
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
    env.pop(k, None)
env['PORT'] = str(PORT)

proc = subprocess.Popen(['node', os.path.join(ROOT, 'deploy', 'server.js')],
                        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding='utf-8', errors='replace')

def wait_up(timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/api/health' % PORT, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False

def http(method, path, body=None, timeout=15):
    url = 'http://127.0.0.1:%d%s' % (PORT, path)
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method=method)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return -1, {'_client_error': str(e)}

try:
    if not wait_up():
        print('[FATAL] server 没起来'); print((proc.stdout.read() or '')[:1500]); sys.exit(2)

    base = 'http://127.0.0.1:%d/' % PORT
    print('=' * 70)
    print('A. Day 22 CRUD 闭环回归（原脚本，未改一个字）')
    print('=' * 70)
    r = subprocess.run([PY, os.path.join(ROOT, 'docs', 'day22', 'evidence', 'verify_crud_cycle.py'), base],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=120)
    print(r.stdout[-2500:])
    if r.stderr.strip():
        print('[stderr]', r.stderr[-600:])

    print('')
    print('=' * 70)
    print('B. 只读接口冒烟')
    print('=' * 70)
    P = F = 0
    def ck(tag, cond, extra=''):
        global P, F
        if cond:
            P += 1; print('  [PASS] %s %s' % (tag, extra))
        else:
            F += 1; print('  [FAIL] %s %s' % (tag, extra))

    for path in ['/api/health', '/api/hot', '/api/favorites',
                 '/api/works?category=music&limit=5', '/api/circles',
                 '/api/original-games', '/api/characters', '/api/originals']:
        st, d = http('GET', path)
        ck('GET ' + path, st == 200, '(HTTP %s)' % st)

    st, _ = http('POST', '/api/favorites', {'workId': 'music-999999'})
    ck('POST 不存在作品 → 404', st == 404, '(HTTP %s)' % st)
    st, _ = http('POST', '/api/favorites', {})
    ck('POST 空 body → 400', st == 400, '(HTTP %s)' % st)

    print('')
    print('冒烟：%d PASS / %d FAIL' % (P, F))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
