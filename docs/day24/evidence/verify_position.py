# -*- coding: utf-8 -*-
"""
Day 24 板块② 定位脚本 —— 排除其他原因，锁定真正根因

做法：起一个本地 server（真库 REST 通道），用真实 HTTP 请求打到 /api/favorites，
      复现「用户看到的错误提示」到底说了什么。

关键对照：同一个 409，两种完全不同的真相
  - 已收藏过        → 409 是**对的**，提示「你已经收藏过 xxx 了」说得通
  - 作品不存在(外键) → 409 是**错的**，用户被告知「你已经收藏过」，但根本没收藏过

用法（在项目根目录）：
  python docs/day24/evidence/verify_position.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PORT = 3099

# ---------- 起 server（REST 通道，读根目录 .env；不用代理） ----------
env = dict(os.environ)
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
    env.pop(k, None)
env['PORT'] = str(PORT)

proc = subprocess.Popen(
    ['node', os.path.join(ROOT, 'deploy', 'server.js')],
    cwd=ROOT, env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8', errors='replace'
)

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
    r = urllib.request.Request(url, data=data,
                               headers={'Content-Type': 'application/json'}, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(r, timeout=timeout) as resp:
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
        print('[FATAL] server 没起来')
        out = proc.stdout.read() if proc.stdout else ''
        print(out[:2000])
        sys.exit(2)

    print('server 已就绪 → http://127.0.0.1:%d' % PORT)

    # 先确认走的确实是 rest（真库）通道
    st, health = http('GET', '/api/health')
    print('health:', st, json.dumps(health, ensure_ascii=False)[:200])

    TS = str(int(time.time()))
    U = 'day24pos-' + TS

    # 拿一个真实存在的 work_id
    st, works = http('GET', '/api/works?limit=1')
    real = works['data'][0]['workId'] if isinstance(works.get('data'), list) and works['data'] else 'music-2'
    print('真实 work_id =', real)
    print('')

    # ===== 场景 1：作品不存在（外键违规）→ 用户看到了什么？=====
    print('#' * 70)
    print('# 场景 1：POST 一个不存在的作品（music-999999）')
    print('#' * 70)
    st1, r1 = http('POST', '/api/favorites', {'userId': U, 'workId': 'music-999999'})
    print('HTTP', st1)
    print(json.dumps(r1, ensure_ascii=False, indent=2))
    print('')

    # ===== 场景 2：重复收藏（唯一冲突）→ 用户看到了什么？=====
    print('#' * 70)
    print('# 场景 2：POST 真实作品两次（第二次是重复收藏）')
    print('#' * 70)
    st2a, r2a = http('POST', '/api/favorites', {'userId': U, 'workId': real})
    print('第一次 HTTP', st2a, json.dumps(r2a, ensure_ascii=False)[:160])
    st2b, r2b = http('POST', '/api/favorites', {'userId': U, 'workId': real})
    print('第二次 HTTP', st2b)
    print(json.dumps(r2b, ensure_ascii=False, indent=2))
    print('')

    print('#' * 70)
    print('# 结论对比')
    print('#' * 70)
    print('场景1（作品不存在）: HTTP %s  error=%s' % (st1, r1.get('error')))
    print('   → 提示语: %s' % r1.get('message'))
    print('场景2（真重复收藏）: HTTP %s  error=%s' % (st2b, r2b.get('error')))
    print('   → 提示语: %s' % r2b.get('message'))
    same = (st1 == st2b) and (r1.get('error') == r2b.get('error'))
    print('')
    print('两种完全不同的真相 → 用户得到完全相同的响应？', '★ 是，这就是 Bug' if same else '否')

    # 清理
    http('DELETE', '/api/favorites?userId=' + U)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
