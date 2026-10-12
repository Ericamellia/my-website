# -*- coding: utf-8 -*-
"""
探测 CloudBase 真库现有表与行数（走 PostgREST，service_role Key）。
用法: python docs/day21/evidence/probe_tables.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENV_PATH = os.path.join(ROOT, 'deploy', '.env')

env = {}
with open(ENV_PATH, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

env_id = env['CLOUDBASE_ENV_ID']
api_key = env['CLOUDBASE_API_KEY']
base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % env_id
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def head(table):
    req = urllib.request.Request(base + table + '?select=*&limit=1', method='HEAD')
    req.add_header('Authorization', 'Bearer ' + api_key)
    req.add_header('Prefer', 'count=exact')
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.headers.get('content-range', '?')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:120]


# 候选表名 = my-app 需要的 9 类 + 已知 4 张
candidates = [
    'works', 'circles', 'favorites', 'hot_videos',
    'music', 'doujin', 'game', 'video', 'art',
    'originals', 'original_games', 'characters',
]

print('表名                状态    行数(content-range)')
print('-' * 58)
for t in candidates:
    st, cr = head(t)
    flag = 'OK ' if st == 200 else 'ERR'
    print('%-18s  %s   %s' % (t, flag, cr))
