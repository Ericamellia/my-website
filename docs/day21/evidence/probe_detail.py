# -*- coding: utf-8 -*-
"""查看 original_games 表列定义 + favorites 当前内容。"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
env = {}
with open(os.path.join(ROOT, 'deploy', '.env'), encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % env['CLOUDBASE_ENV_ID']
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(q):
    req = urllib.request.Request(base + q)
    req.add_header('Authorization', 'Bearer ' + env['CLOUDBASE_API_KEY'])
    with opener.open(req, timeout=25) as r:
        return json.load(r)


print('=== favorites 全部行 ===')
try:
    rows = get('favorites?select=*&order=id')
    for r in rows:
        print('  #%s %s  %s' % (r.get('id'), r.get('work_id'), (r.get('note') or '')[:30]))
    print('  共 %d 条' % len(rows))
except Exception as e:
    print('  ERR', e)

for t in ['original_games', 'original_game_categories', 'characters', 'originals']:
    print('\n=== %s 行数 ===' % t)
    try:
        rows = get(t + '?select=*&limit=3')
        print('  前 3 行:', json.dumps(rows, ensure_ascii=False)[:400])
    except Exception as e:
        print('  ERR', e)
