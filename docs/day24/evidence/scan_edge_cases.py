# -*- coding: utf-8 -*-
"""
Day 24 板块① 补充扫描 —— 用刁钻输入找可稳定复现的真实 Bug

用户指示（卡住降级）：用空值、超长文本、快速连点等刁钻输入生成补充测试用例。

本脚本对真库（PostgREST）直接发请求，逐一探测边界，
把「异常但没人管」的响应挑出来。
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_env(path):
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env(os.path.join(ROOT, '.env'))
ENV.update(load_env(os.path.join(ROOT, 'deploy', '.env')))
BASE = 'https://' + ENV['CLOUDBASE_ENV_ID'] + '.api.tcloudbasegateway.com/v1/rdb/rest/'
KEY = ENV['CLOUDBASE_API_KEY']


def req(method, table, query=None, body=None, prefer=None, timeout=15):
    url = BASE + table
    if query:
        parts = [urllib.parse.quote(str(k), safe='') + '=' + urllib.parse.quote(str(v), safe='')
                 for k, v in query.items() if v is not None]
        if parts:
            url += '?' + '&'.join(parts)
    headers = {'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}
    if prefer:
        headers['Prefer'] = prefer
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return -1, {'_client_error': str(e)}


TS = str(int(time.time()))
U = 'day24scan-' + TS

print('补充扫描 · user_id =', U)
print('')

# 找一个真实 work_id
st, w = req('GET', 'works', {'select': 'work_id', 'limit': '1'})
REAL = w[0]['work_id']
print('真实 work_id =', REAL)
print('')

results = []


def probe(tag, method, table, **kw):
    st, d = req(method, table, **kw)
    body = json.dumps(d, ensure_ascii=False) if not isinstance(d, str) else d
    results.append((tag, st, body))
    print('%-46s HTTP %-4s %s' % (tag, st, body[:110]))
    return st, d


print('---- 1. PATCH 复活：对不存在的行做 PATCH（找不存在的东西）----')
# 模拟 addFavoriteToRest 第一步：PATCH 一个「不存在」的软删行
probe('PATCH 不存在的软删行', 'PATCH', 'favorites',
      query={'user_id': 'eq.' + U, 'work_id': 'eq.' + REAL,
             'is_deleted': 'eq.true', 'limit': '1', 'select': 'id,user_id,work_id'},
      body={'is_deleted': False}, prefer='return=representation')

print('')
print('---- 2. 超长 note（255 上限，后端该拦）----')
probe('note=300 字（应被后端挡）', 'POST', 'favorites',
      query={'select': 'id'},
      body={'user_id': U, 'work_id': REAL, 'note': 'x' * 300},
      prefer='return=representation')

print('')
print('---- 3. 空字符串 work_id ----')
probe('workId="" ', 'POST', 'favorites',
      query={'select': 'id'},
      body={'user_id': U, 'work_id': ''},
      prefer='return=representation')

print('')
print('---- 4. 快速连点：同一 (user,work) 并发 3 发 ----')
# 先建一条
probe('建一条基准', 'POST', 'favorites', query={'select': 'id'},
      body={'user_id': U, 'work_id': REAL}, prefer='return=representation')
# 再连发 3 次
for i in range(3):
    probe('连点第 %d 发' % (i + 1), 'POST', 'favorites', query={'select': 'id'},
          body={'user_id': U, 'work_id': REAL}, prefer='return=representation')

print('')
print('---- 5. 重复收藏时读回的条目（检查 JOIN 字段是否缺失）----')
st, dup = req('GET', 'favorites', {
    'select': 'id,user_id,work_id,note,created_at',   # ← 复刻 index.js:304 的 select
    'user_id': 'eq.' + U, 'work_id': 'eq.' + REAL, 'is_deleted': 'eq.false', 'limit': '1'
})
print('复刻 index.js:304 的 select（无 JOIN）→', st, json.dumps(dup, ensure_ascii=False)[:200])

st2, full = req('GET', 'favorites', {
    'select': 'id,user_id,work_id,note,created_at,'
              'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
    'user_id': 'eq.' + U, 'work_id': 'eq.' + REAL, 'is_deleted': 'eq.false', 'limit': '1'
})
print('带 JOIN 的 select            →', st2, json.dumps(full, ensure_ascii=False)[:260])
print('')
print('>>> 对比：无 JOIN 的返回里有 name 吗？',
      '有' if (isinstance(dup, list) and dup and 'name' in dup[0]) else '没有 ← 条目会退化成 (作品已下架)')

# 清理
req('DELETE', 'favorites', {'user_id': 'eq.' + U})
print('')
print('清理完成')

out = os.path.join(ROOT, 'docs', 'day24', 'evidence', 'scan-edge-cases-output.txt')
with open(out, 'w', encoding='utf-8') as f:
    f.write('Day 24 补充扫描结果\n')
    f.write('user_id = %s\n\n' % U)
    for tag, st, body in results:
        f.write('%-46s HTTP %-4s %s\n' % (tag, st, body))
print('已写入', out)
