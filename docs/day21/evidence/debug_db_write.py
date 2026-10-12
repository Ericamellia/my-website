# -*- coding: utf-8 -*-
"""排查「改库后页面没变」：逐层确认是哪一层的问题。"""
import json, urllib.request, os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
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


ORIG = 'ハルトマンの妖怪少女'
MARK = '★改库测试★'

print('=' * 70)
print('逐层排查：改库 → 页面')
print('=' * 70)
print()
print('【第 1 层】真库本身（直接用 REST 读）')
_, r = rest('GET', 'works', 'select=work_id,name&work_id=eq.music-1')
print('    改前:', r[0]['name'])
st, _ = rest('PATCH', 'works', 'work_id=eq.music-1', {'name': MARK}, 'return=minimal')
time.sleep(1.5)
_, r = rest('GET', 'works', 'select=work_id,name&work_id=eq.music-1')
print('    PATCH 状态 %s，改后:' % st, r[0]['name'])
print('    → 库里确实改了 ?', '✅' if r[0]['name'] == MARK else '❌')
print()

print('【第 2 层】PostgREST 是否有缓存 / 读副本延迟')
for i in range(3):
    _, r = rest('GET', 'works', 'select=name&work_id=eq.music-1')
    print('    第 %d 次读:' % (i + 1), r[0]['name'])
    time.sleep(0.8)
print()

# 还原
rest('PATCH', 'works', 'work_id=eq.music-1', {'name': ORIG}, 'return=minimal')
time.sleep(1)
_, r = rest('GET', 'works', 'select=name&work_id=eq.music-1')
print('已还原:', r[0]['name'])
