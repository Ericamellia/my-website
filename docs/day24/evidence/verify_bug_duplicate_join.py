# -*- coding: utf-8 -*-
"""
Day 24 板块①/④ —— 主 Bug 端到端复现 + 验证脚本

主 Bug（候选）：POST /api/favorites 走「重复收藏」分支时，
  返回的 data 条目缺 JOIN，name/tags/characters 等字段全丢，
  前端卡片会显示成 "(作品已下架)"。

对照：
  第一次 POST（201 created） → data.name = 真实作品名
  第二次 POST（409 duplicate）→ data.name = "(作品已下架)"   ← 同一个作品，名字却变了

用法：
  python docs/day24/evidence/verify_bug_duplicate_join.py          # 复现（修复前）
  python docs/day24/evidence/verify_bug_duplicate_join.py --fix    # 验证（修复后）
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PORT = 3098
MODE = '修复后' if '--fix' in sys.argv else '修复前'

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

PASS = FAIL = 0
def check(tag, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  [PASS] %s %s' % (tag, extra))
    else:
        FAIL += 1
        print('  [FAIL] %s %s' % (tag, extra))

try:
    if not wait_up():
        print('[FATAL] server 没起来'); print((proc.stdout.read() or '')[:1500]); sys.exit(2)

    print('=' * 70)
    print('Day 24 主 Bug 复现/验证 —— 模式：%s' % MODE)
    print('=' * 70)

    TS = str(int(time.time()))
    U = 'day24bug-' + TS

    st, works = http('GET', '/api/works?limit=1')
    real = works['data'][0]['workId']
    expect_name = works['data'][0].get('name')
    print('测试作品 workId=%s  name=%s' % (real, expect_name))
    print('')

    # ---- 第一次：应 201，条目带完整作品信息 ----
    print('① 第一次收藏（201 created）')
    st1, r1 = http('POST', '/api/favorites', {'userId': U, 'workId': real})
    print('   HTTP', st1)
    d1 = r1.get('data') or {}
    print('   data.name =', repr(d1.get('name')))
    print('   data.tags =', repr(d1.get('tags')))
    check('第一次收藏成功', st1 == 201, '(HTTP %s)' % st1)
    check('第一次条目带真实作品名', d1.get('name') == expect_name,
          '(得到 %r，期望 %r)' % (d1.get('name'), expect_name))
    print('')

    # ---- 第二次：重复，409 duplicate，条目也应是同一个作品 ----
    print('② 第二次收藏同一作品（409 duplicate）')
    st2, r2 = http('POST', '/api/favorites', {'userId': U, 'workId': real})
    print('   HTTP', st2)
    d2 = r2.get('data') or {}
    print('   data.name =', repr(d2.get('name')))
    print('   data.tags =', repr(d2.get('tags')))
    check('重复收藏被识别', st2 == 409 and r2.get('error') == 'already_favorited',
          '(HTTP %s error=%s)' % (st2, r2.get('error')))
    print('')
    print('   ★ 核心断言：两次返回的 name 必须一致（同一作品）')
    check('重复分支也返回真实作品名', d2.get('name') == expect_name,
          '(得到 %r，期望 %r)' % (d2.get('name'), expect_name))
    check('重复分支 name 不是「(作品已下架)」', d2.get('name') != '(作品已下架)',
          '(得到 %r)' % (d2.get('name'),))

    # 清理
    http('DELETE', '/api/favorites?userId=' + U)

    print('')
    print('=' * 70)
    print('结果：%d PASS / %d FAIL   （模式：%s）' % (PASS, FAIL, MODE))
    print('=' * 70)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
